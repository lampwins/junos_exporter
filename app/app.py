from jnpr.junos import Device
from lxml import etree
import re
from cgi import escape, parse_qs
import json
import yaml
import logging


logger = logging.getLogger(__name__)

config = None


class Metrics(object):
    """
    Store metrics and do conversions to PromQL syntax
    """

    class _Metric(object):
        """
        This is an actual metric entity
        """

        def __init__(self, name, value, metric_type, labels=None):
            self.name = name
            self.value = float(value)
            self.metric_type = metric_type
            self.labels = []
            if labels:
                for label_name, label_value in labels.items():
                    self.labels.append('{}="{}"'.format(label_name, label_value))

        def __str__(self):
            return "{}{} {}".format(self.name, "{" + ",".join(self.labels) + "}", self.value)

    def __init__(self):
        self._metrics_registry = {}
        self._metric_types = {}

    def register(self, name, metric_type):
        """
        Add a metric to the registry
        """
        if self._metrics_registry.get(name) is None:
            self._metrics_registry[name] = []
            self._metric_types[name] = metric_type
        else:
            raise ValueError('Metric named {} is already registered.'.format(name))

    def add_metric(self, name, value, labels=None):
        """
        Add a new metric
        """
        collector = self._metrics_registry.get(name)
        if collector is None:
            raise ValueError('Metric named {} is not registered.'.format(name))

        metric = self._Metric(name, value, self._metric_types[name], labels)
        collector.append(metric)

    def collect(self):
        """
        Collect all metrics and return
        """
        lines = []
        for name, metric_type in self._metric_types.items():
            lines.append("# TYPE {} {}".format(name, metric_type))
            lines.extend(self._metrics_registry[name])
        return "\n".join([str(x) for x in lines]) + '\n'


def hello(environ, start_response):
    """Like the example above, but it uses the name specified in the
URL."""
    # get the name from the url if it was specified there.
    args = environ['myapp.url_args']
    if args:
        subject = escape(args[0])
    else:
        subject = 'World'
    start_response('200 OK', [('Content-Type', 'text/html')])
    return ['''Hello %(subject)s
            Hello %(subject)s!

''' % {'subject': subject}]

def not_found(environ, start_response):
    """Called if no URL matches."""
    start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
    return [bytes('Not Found', 'utf-8')]


def get_interface_metrics(registry, dev):
    """
    Get interface metrics
    """

    # interfaces
    interface_information = dev.rpc.get_interface_information(extensive=True)

    # register interface metrics
    registry.register('ifaceInputBps', 'gauge')
    registry.register('ifaceOutputBps', 'gauge')
    registry.register('ifaceInputBytes', 'gauge')
    registry.register('ifaceOutputBytes', 'gauge')
    registry.register('ifaceInputErrors', 'gauge')
    registry.register('ifaceOutputErrors', 'gauge')
    registry.register('ifaceInputDrops', 'gauge')
    registry.register('ifaceOutputDrops', 'gauge')
    registry.register('ifaceCarrierTransitions', 'gauge')
    registry.register('ifaceUp', 'gauge')

    # interface metics
    for interface in interface_information.findall('physical-interface'):

        interface_name = interface.find('name').text.strip()

        # input bps
        input_bps = interface.find('traffic-statistics/input-bps')
        if input_bps is not None:
            registry.add_metric('ifaceInputBps', input_bps.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceInputBps', 0.0, {'ifName': interface_name})

        # output bps
        output_bps = interface.find('traffic-statistics/output-bps')
        if output_bps is not None:
            registry.add_metric('ifaceOutputBps', output_bps.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceOutputBps', 0.0, {'ifName': interface_name})

        # input bytes
        input_bytes = interface.find('traffic-statistics/input-bytes')
        if input_bytes is not None:
            registry.add_metric('ifaceInputBytes', input_bytes.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceInputBytes', 0.0, {'ifName': interface_name})

        # output bps
        output_bytes = interface.find('traffic-statistics/output-bytes')
        if output_bytes is not None:
            registry.add_metric('ifaceOutputBytes', output_bytes.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceOutputBytes', 0.0, {'ifName': interface_name})

        # status
        status = interface.find('oper-status')
        if status.text.strip() == 'up':
            registry.add_metric('ifaceUp', 1.0, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceUp', 0.0, {'ifName': interface_name})

        # input errors
        input_errors = interface.find('input-error-list/input-errors')
        if input_errors is not None:
            registry.add_metric('ifaceInputErrors', input_errors.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceInputErrors', 0.0, {'ifName': interface_name})

        # output errors
        output_errors = interface.find('output-error-list/output-errors')
        if output_errors is not None:
            registry.add_metric('ifaceOutputErrors', output_errors.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceOutputErrors', 0.0, {'ifName': interface_name})

        # input drops
        input_drops = interface.find('input-error-list/input-drops')
        if input_drops is not None:
            registry.add_metric('ifaceInputDrops', input_drops.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceInputDrops', 0.0, {'ifName': interface_name})

        # output drops
        output_drops = interface.find('output-error-list/output-drops')
        if output_drops is not None:
            registry.add_metric('ifaceOutputDrops', output_drops.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceOutputDrops', 0.0, {'ifName': interface_name})

        # output carrier transitions
        output_carrier_transitions = interface.find('output-error-list/carrier-transitions')
        if output_drops is not None:
            registry.add_metric('ifaceCarrierTransitions', output_carrier_transitions.text, {'ifName': interface_name})
        else:
            registry.add_metric('ifaceCarrierTransitions', 0.0, {'ifName': interface_name})

        # logical interfaces
        for logical_interface in interface.findall('logical-interface'):

            logical_interface_name = logical_interface.find('name').text.strip()

            # for logical interfaces we look at transit traffic

            # input bps
            input_bps = logical_interface.find('transit-traffic-statistics/input-bps')
            if input_bps is not None:
                registry.add_metric('ifaceInputBps', input_bps.text, {'ifName': logical_interface_name, 'transit': 1})
            else:
                registry.add_metric('ifaceInputBps', 0.0, {'ifName': logical_interface_name, 'transit': 1})

            # output bps
            output_bps = logical_interface.find('transit-traffic-statistics/output-bps')
            if output_bps is not None:
                registry.add_metric('ifaceOutputBps', output_bps.text, {'ifName': logical_interface_name, 'transit': 1})
            else:
                registry.add_metric('ifaceOutputBps', 0.0, {'ifName': logical_interface_name, 'transit': 1})

            # input bytes
            input_bytes = logical_interface.find('transit-traffic-statistics/input-bytes')
            if input_bytes is not None:
                registry.add_metric('ifaceInputBytes', input_bytes.text, {'ifName': logical_interface_name, 'transit': 1})
            else:
                registry.add_metric('ifaceInputBytes', 0.0, {'ifName': logical_interface_name, 'transit': 1})

            # output bps
            output_bytes = logical_interface.find('transit-traffic-statistics/output-bytes')
            if output_bytes is not None:
                registry.add_metric('ifaceOutputBytes', output_bytes.text, {'ifName': logical_interface_name, 'transit': 1})
            else:
                registry.add_metric('ifaceOutputBytes', 0.0, {'ifName': logical_interface_name, 'transit': 1})


def get_environment_metrics(registry, dev):
    """
    Get environment metrics
    """

    # envornment
    environment_information = dev.rpc.get_environment_information()

    # register env metrics
    registry.register('environmentItem', 'gauge')

    for env_item in environment_information.findall('environment-item'):

        status = 1.0 if env_item.find('status').text.strip() == 'OK' else 0.0
        name = env_item.find('name').text.strip()
        _class = env_item.find('class')
        if _class is not None:
            _class = _class.text.strip()
            registry.add_metric('environmentItem', status, {'name': name, 'class': _class})
        else:
            registry.add_metric('environmentItem', status, {'name': name})


def get_virtual_chassis_metrics(registry, dev):
    """
    Get virtual chassis metrics
    """

        # virtual chassis
    vc_information = dev.rpc.get_virtual_chassis_information()

    # register virtual chassis metrics
    registry.register('virtualChassisMemberStatus', 'gauge')

    for vc_member in vc_information.findall('member-list/member'):

        status_text = vc_member.find('member-status').text.strip()
        status = 1.0 if status_text == 'Prsnt' else 0.0
        serial = vc_member.find('member-serial-number').text
        if serial is not None:
            serial = serial.strip()
        else:
            serial = "unknown"
        model = vc_member.find('member-model').text
        member_id = vc_member.find('member-id').text.strip()
        role = vc_member.find('member-role')
        if role is not None:
            role = role.text.strip()
        else:
            role = "unknown"
        registry.add_metric('virtualChassisMemberStatus', status, {'status': status_text, 'serial': serial, 'model': model, 'id': member_id, 'role': role})

    # virtual chassis ports
    vc_port_information = dev.rpc.get_virtual_chassis_port_information()

    # register virtual chassis port metrics
    registry.register('virtualChassisPortStatus', 'gauge')

    for fpc in vc_port_information.findall('multi-routing-engine-item'):

        fpc_name = fpc.find('re-name').text.strip()

        for vc_port in fpc.findall('virtual-chassis-port-information/port-list/port-information'):

            status_text = vc_port.find('port-status').text.strip()
            status = 1.0 if status_text == 'Up' else 0.0
            #neighbor_id = vc_port.find('neighbor-id').text.strip()
            port_name = vc_port.find('port-name').text.strip()
            #neighbor_port_name = vc_port.find('neighbor-interface').text.strip()
            #registry.add_metric('virtualChassisPortStatus', status, {'fpc': fpc_name, 'status': status_text, 'neighbor-id': neighbor_id, 'port-name': port_name, 'neighbor-port': neighbor_port_name})
            registry.add_metric('virtualChassisPortStatus', status, {'fpc': fpc_name, 'status': status_text, 'portName': port_name})


def get_route_engine_metrics(registry, dev):
    """
    Get Routing engine metrics
    """

    # routing engine data
    route_engines = dev.rpc.get_route_engine_information()

    # register virtual chassis port metrics
    registry.register('cpuUsage', 'gauge')
    registry.register('memoryUsage', 'gauge')
    registry.register('cpuTemp', 'gauge')
    registry.register('chassisTemp', 'gauge')
    registry.register('startTime', 'gauge')
    registry.register('upTime', 'gauge')

    for route_engine in route_engines.findall('route-engine'):

        fpc = route_engine.find('slot')
        if fpc is not None:
            meta = {
                'fpc': fpc.text.strip()
            }
        else:
            # not fpc based
            meta = {}

        # temp
        temp_element = route_engine.find('temperature')
        if temp_element is not None:
            temp_f = temp_element.text.strip().split('/')[1].split(' ')[1]
            registry.add_metric('chassisTemp', temp_element.attrib['celsius'], {**meta, **{'fahrenheit': temp_f}})

            # cpu temp
            temp_f = route_engine.find('cpu-temperature')
            if temp_f is not None:
                temp_f = temp_f.text.strip().split('/')[1].split(' ')[1]
                registry.add_metric('cpuTemp', route_engine.find('cpu-temperature').attrib['celsius'], {**meta, **{'fahrenheit': temp_f}})

        # cpu
        cpu_user = route_engine.find('cpu-user').text.strip()
        cpu_background = route_engine.find('cpu-background').text.strip()
        cpu_system = route_engine.find('cpu-system').text.strip()
        cpu_interrupt = route_engine.find('cpu-interrupt').text.strip()
        cpu_idle = route_engine.find('cpu-idle').text.strip()

        registry.add_metric('cpuUsage', cpu_user, {**meta, **{'type': 'user'}})
        registry.add_metric('cpuUsage', cpu_background, {**meta, **{'type': 'background'}})
        registry.add_metric('cpuUsage', cpu_system, {**meta, **{'type': 'system'}})
        registry.add_metric('cpuUsage', cpu_interrupt, {**meta, **{'type': 'interrupt'}})
        registry.add_metric('cpuUsage', cpu_idle, {**meta, **{'type': 'idle'}})
        registry.add_metric('cpuUsage', int(cpu_user) + int(cpu_background) + int(cpu_system) + int(cpu_interrupt), {**meta, **{'type': 'total'}})

        # memory
        registry.add_metric('memoryUsage', route_engine.find('memory-buffer-utilization').text.strip(), meta)

        # time
        registry.add_metric('startTime', route_engine.find('start-time').attrib['seconds'], meta)
        registry.add_metric('upTime', route_engine.find('up-time').attrib['seconds'], meta)


def get_storage_metrics(registry, dev):
    """
    Get system storage metrics
    """

    # storage data
    multi_routing_engine_results = dev.rpc.get_system_storage()

    # register virtual chassis port metrics
    registry.register('fileSystemBlocksTotal', 'gauge')
    registry.register('fileSystemBlocksUsed', 'gauge')

    for multi_routing_engine_item in multi_routing_engine_results.findall('multi-routing-engine-item'):

        fpc = multi_routing_engine_item.find('re-name').text.strip()

        for filesytem in multi_routing_engine_item.findall('system-storage-information/filesystem'):

            filesystem_name = filesytem.find('filesystem-name').text.strip()
            total_blocks = filesytem.find('total-blocks').text.strip()
            used_blocks = filesytem.find('used-blocks').text.strip()
            mount_point = filesytem.find('mounted-on').text.strip()

            registry.add_metric('fileSystemBlocksTotal', total_blocks, {'fpc': fpc, 'filesystem': filesystem_name, 'mountpoint': mount_point})
            registry.add_metric('fileSystemBlocksUsed', used_blocks, {'fpc': fpc, 'filesystem': filesystem_name, 'mountpoint': mount_point})


def get_bgp_metrics(registry, dev):
    """
    Get BGP neighbor metrics
    """

    # Based on the order in which states are defined in the
    # BGP FSA in RFC4271 section 8.2.2
    _peer_state_values = {
        'Idle': 1,
        'Connect': 2,
        'Active': 3,
        'OpenSent': 4,
        'OpenConfirm': 5,
        'Established': 6
    }

    # bgp neighbor data
    bgp_results = dev.rpc.get_bgp_neighbor_information()

    # register bgp metrics
    registry.register('bgpPeerCount', 'gauge')
    registry.register('bgpPeerState', 'gauge')
    registry.register('bgpPeerLastState', 'gauge')
    registry.register('bgpPeerOptionHoldtime', 'gauge')
    registry.register('bgpPeerOptionPreference', 'gauge')
    registry.register('bgpPeerFlapCount', 'gauge')
    registry.register('bgpPeerActivePrefixCount', 'gauge')
    registry.register('bgpPeerReceivedPrefixCount', 'gauge')
    registry.register('bgpPeerAcceptedPrefixCount', 'gauge')
    registry.register('bgpPeerSuppressedPrefixCount', 'gauge')
    registry.register('bgpPeerAdvertisedPrefixCount', 'gauge')
    registry.register('bgpPeerLastReceived', 'gauge')
    registry.register('bgpPeerLastSent', 'gauge')
    registry.register('bgpPeerLastChecked', 'gauge')
    registry.register('bgpPeerInputMessages', 'gauge')
    registry.register('bgpPeerInputUpdates', 'gauge')
    registry.register('bgpPeerInputRefreshes', 'gauge')
    registry.register('bgpPeerInputOctets', 'gauge')
    registry.register('bgpPeerOutputMessages', 'gauge')
    registry.register('bgpPeerOutputUpdates', 'gauge')
    registry.register('bgpPeerOutputRefreshes', 'gauge')
    registry.register('bgpPeerOutputOctets', 'gauge')
    registry.register('bgpErrorSendCount', 'gauge')
    registry.register('bgpErrorReceiveCount', 'gauge')

    peers = bgp_results.findall('bgp-peer')
    registry.add_metric('bgpPeerCount', len(peers))

    for peer in peers:

        peer_address = peer.find('peer-address').text
        peer_as = peer.find('peer-as').text
        local_address = peer.find('local-address').text
        local_as = peer.find('local-as').text
        meta = {
            'peerAddress': peer_address,
            'localAddress': local_address,
            'peerAS': peer_as,
            'localAS': local_as 
        }

        peer_state_text = peer.find('peer-state').text
        peer_state = _peer_state_values[peer_state_text]
        last_state_text = peer.find('last-state').text
        last_state = _peer_state_values[last_state_text]

        # state metrics
        registry.add_metric('bgpPeerState', peer_state, {**meta, **{'state': peer_state_text,'lastState': last_state_text}})
        registry.add_metric('bgpPeerLastState', last_state, {**meta, **{'lastState': last_state_text, 'state': peer_state_text}})

        # holdtime option
        hold_time = peer.find('bgp-option-information/holdtime')
        if hold_time is not None:
            registry.add_metric('bgpPeerOptionHoldtime', hold_time.text, meta)

        # preference option
        preference = peer.find('bgp-option-information/preference')
        if preference is not None:
            registry.add_metric('bgpPeerOptionPreference', preference.text, meta)

        # flap counts
        flap_count = peer.find('flap-count')
        last_flap_event = peer.find('last-flap-event')
        if flap_count is not None:
            if last_flap_event is not None:
                registry.add_metric('bgpPeerFlapCount', flap_count.text, {**meta, **{'lastFlapEvent': last_flap_event.text}})
            else:
                registry.add_metric('bgpPeerFlapCount', flap_count.text, meta)

        # rib metrics
        for rib in peer.findall('bgp-rib'):

            rib_name = rib.find('name').text
            rib_meta = {'ribName': rib_name}
            rib_meta = {**rib_meta, **meta}

            active_prefix_count = rib.find('active-prefix-count').text
            received_prefix_count = rib.find('received-prefix-count').text
            accepted_prefix_count = rib.find('accepted-prefix-count').text
            suppressed_prefix_count = rib.find('suppressed-prefix-count').text
            advertised_prefix_count = rib.find('advertised-prefix-count').text

            registry.add_metric('bgpPeerActivePrefixCount', active_prefix_count, rib_meta)
            registry.add_metric('bgpPeerReceivedPrefixCount', received_prefix_count, rib_meta)
            registry.add_metric('bgpPeerAcceptedPrefixCount', accepted_prefix_count, rib_meta)
            registry.add_metric('bgpPeerSuppressedPrefixCount', suppressed_prefix_count, rib_meta)
            registry.add_metric('bgpPeerAdvertisedPrefixCount', advertised_prefix_count, rib_meta)

        # stats
        last_received = peer.find('last-received')
        if last_received is not None:
            registry.add_metric('bgpPeerLastReceived', last_received.text, meta)

        last_sent = peer.find('last-sent')
        if last_sent is not None:
            registry.add_metric('bgpPeerLastSent', last_sent.text, meta)

        last_checked = peer.find('last-checked')
        if last_checked is not None:
            registry.add_metric('bgpPeerLastChecked', last_checked.text, meta)

        input_messages = peer.find('input-messages')
        if input_messages is not None:
            registry.add_metric('bgpPeerInputMessages', input_messages.text, meta)

        input_updates = peer.find('input-updates')
        if input_updates is not None:
            registry.add_metric('bgpPeerInputUpdates', input_updates.text, meta)

        input_refreshes = peer.find('input-refreshes')
        if input_refreshes is not None:
            registry.add_metric('bgpPeerInputRefreshes', input_refreshes.text, meta)

        input_octets = peer.find('input-octets')
        if input_octets is not None:
            registry.add_metric('bgpPeerInputOctets', input_octets.text, meta)

        output_messages = peer.find('output-messages')
        if output_messages is not None:
            registry.add_metric('bgpPeerOutputMessages', output_messages.text, meta)

        output_updates = peer.find('output-updates')
        if output_updates is not None:
            registry.add_metric('bgpPeerOutputUpdates', output_updates.text, meta)

        output_refreshes = peer.find('output-refreshes')
        if output_refreshes is not None:
            registry.add_metric('bgpPeerOutputRefreshes', output_refreshes.text, meta)

        output_octets = peer.find('output-octets')
        if output_octets is not None:
            registry.add_metric('bgpPeerOutputOctets', output_octets.text, meta)

        # errors
        for error in peer.findall('bgp-error'):

            error_name = error.find('name').text
            error_meta = {'errorName': error_name}
            error_meta = {**error_meta, **meta}

            send_count = error.find('send-count').text
            receive_count = error.find('receive-count').text

            registry.add_metric('bgpErrorSendCount', send_count, error_meta)
            registry.add_metric('bgpErrorReceiveCount', receive_count, error_meta)


def metrics(environ, start_response):

    # load config
    with open('junos_exporter.yaml', 'r') as f:
        config = yaml.load(f)

    # parameters from url
    parameters = parse_qs(environ.get('QUERY_STRING', ''))

    # get profile from config
    profile = config[parameters['module'][0]]

    # open device connection
    if profile['auth']['method'] == 'password':
        # using regular username/password
        dev = Device(host=parameters['target'][0],
                     user=profile['auth']['username'],
                     password=profile['auth']['password'])
    elif profile['auth']['method'] == 'ssh_key':
        # using ssh key
        dev = Device(host=parameters['target'][0],
                     user=profile['auth']['username'],
                     password=profile['auth'].get('password'),
                     ssh_private_key_file='./ssh_private_key_file')
    dev.open()

    # create metrics registry
    registry = Metrics()

    # get and parse metrics
    types = profile['metrics']
    if 'interface' in types:
        get_interface_metrics(registry, dev)
    if 'environment' in types:
        get_environment_metrics(registry, dev)
    if 'virtual_chassis' in types:
        get_virtual_chassis_metrics(registry, dev)
    if 'routing_engine' in types:
        get_route_engine_metrics(registry, dev)
    if 'storage' in types:
        get_storage_metrics(registry, dev)
    if 'bgp' in types:
        get_bgp_metrics(registry, dev)

    # start response
    data = registry.collect()
    status = '200 OK'
    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-Length', str(len(data)))
    ]
    start_response(status, response_headers)
    return [bytes(data, 'utf-8')]


# map urls to functions
urls = [
    #(r'metrics$', self_service),
    #(r'metrics/$', self_service),
    (r'metrics/?$', metrics),
    (r'metrics/(.+)$', metrics)
]

def app(environ, start_response):
    """
    The main WSGI application. Dispatch the current request to
    the functions from above and store the regular expression
    captures in the WSGI environment as  `myapp.url_args` so that
    the functions from above can access the url placeholders.

    If nothing matches call the `not_found` function.
    """
    path = environ.get('PATH_INFO', '').lstrip('/')
    for regex, callback in urls:
        match = re.search(regex, path)
        if match is not None:
            environ['app.url_args'] = match.groups()
            return callback(environ, start_response)
    return not_found(environ, start_response)
