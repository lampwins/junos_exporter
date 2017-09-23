from jnpr.junos import Device
from lxml import etree
import re
from cgi import escape, parse_qs
import json
import yaml
import logging


logger = logging.getLogger(__name__)


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


def metrics(environ, start_response):

    with open('junos_exporter.yaml', 'r') as f:
        config = yaml.load(f)

    parameters = parse_qs(environ.get('QUERY_STRING', ''))

    profile = config[parameters['module'][0]]

    dev = Device(host=parameters['target'][0], user=profile['auth']['username'], password=profile['auth']['password'])
    dev.open()
    interface_information = dev.rpc.get_interface_information(extensive=True)

    registry = Metrics()

    # register interface metrics
    registry.register('ifaceInputBps', 'gauge')
    registry.register('ifaceOutputBps', 'gauge')
    registry.register('ifaceInputBytes', 'gauge')
    registry.register('ifaceOutputBytes', 'gauge')
    registry.register('ifaceInputErrors', 'gauge')
    registry.register('ifaceOutputErrors', 'gauge')
    registry.register('ifaceInputDrops', 'gauge')
    registry.register('ifaceOutputDrops', 'gauge')
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

    # envornment
    environment_information = dev.rpc.get_environment_information()

    # register env metrics
    registry.register('environmentItem', 'gauge')

    for env_item in environment_information.findall('environment-item'):

        status = 1.0 if env_item.find('status').text.strip() == 'OK' else 0.0
        name = env_item.find('name').text.strip()
        _class = env_item.find('class').text.strip()
        registry.add_metric('environmentItem', status, {'name': name, 'class': _class})

    # virtual chassis
    vc_information = dev.rpc.get_virtual_chassis_information()

    # register virtual chassis metrics
    registry.register('virtualChassisMemberStatus', 'gauge')

    for vc_member in vc_information.findall('member-list/member'):

        status_text = vc_member.find('member-status').text.strip()
        status = 1.0 if status_text == 'Prsnt' else 0.0
        serial = vc_member.find('member-serial-number').text.strip()
        model = vc_member.find('member-model').text.strip()
        member_id = vc_member.find('member-id').text.strip()
        role = vc_member.find('member-role').text.strip()
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

        fpc = route_engine.find('slot').text.strip()

        # temp
        temp_f = route_engine.find('temperature').text.strip().split('/')[1].split(' ')[1]
        registry.add_metric('chassisTemp', route_engine.find('temperature').attrib['celsius'], {'fpc': fpc, 'fahrenheit': temp_f})

        # cpu temp
        temp_f = route_engine.find('cpu-temperature').text.strip().split('/')[1].split(' ')[1]
        registry.add_metric('cpuTemp', route_engine.find('cpu-temperature').attrib['celsius'], {'fpc': fpc, 'fahrenheit': temp_f})

        # cpu
        cpu_user = route_engine.find('cpu-user').text.strip()
        cpu_background = route_engine.find('cpu-background').text.strip()
        cpu_system = route_engine.find('cpu-system').text.strip()
        cpu_interrupt = route_engine.find('cpu-interrupt').text.strip()
        cpu_idle = route_engine.find('cpu-idle').text.strip()

        registry.add_metric('cpuUsage', cpu_user, {'fpc': fpc, 'type': 'user'})
        registry.add_metric('cpuUsage', cpu_background, {'fpc': fpc, 'type': 'background'})
        registry.add_metric('cpuUsage', cpu_system, {'fpc': fpc, 'type': 'system'})
        registry.add_metric('cpuUsage', cpu_interrupt, {'fpc': fpc, 'type': 'interrupt'})
        registry.add_metric('cpuUsage', cpu_idle, {'fpc': fpc, 'type': 'idle'})
        registry.add_metric('cpuUsage', int(cpu_user) + int(cpu_background) + int(cpu_system) + int(cpu_interrupt), {'fpc': fpc, 'type': 'total'})

        # memory
        registry.add_metric('memoryUsage', route_engine.find('memory-buffer-utilization').text.strip(), {'fpc': fpc})

        # time
        registry.add_metric('startTime', route_engine.find('start-time').attrib['seconds'], {'fpc': fpc})
        registry.add_metric('upTime', route_engine.find('up-time').attrib['seconds'], {'fpc': fpc})

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
