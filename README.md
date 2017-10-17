# Junos Exporter
Junos Exporter is a Prometheus exporter that uses the Juniper junos-eznc python library to gather metrics via netconf rpc's rather than snmp.

It follows many of the same tenants as the snmp_exporter. So the scrape config in prometheus will be almost identical. To that end, we expect two url parameters for a scrape request. `module` is the config module defined in the config file that contains authentication parameters and metric collection settings. `target` is the host that should be scraped.

## Deployment
Junos Exporter ships as a docker container and this repo comes with a docker compose definition which puts the gunicorn wsgi app behind a nginx instance.

To deploy follow these steps:

0. Install `docker` and `docker-compose`.
1. Clone this repo (usually into a new directory in opt such as `/opt/junos_exporter`).
```
git clone https://github.com/lampwins/junos_exporter /opt/junos_exporter
```
2. Copy the config file and edit as necessary (see section on config file).
```
cp junos_exporter.example.yaml /etc/junos_exporter/junos_exporter.yaml
```
3. (For systemd boxes) Copy systemd service. For non systemd, good luck. Note that the service is set to run as the `prometheus` user.
```
cp ./extras/junos_exporter.service /etc/systemd/system/junos_exporter.service
```
4. Load, enable and start the service
```
systemctl daemon-reload
systemctl enable junos_exporter
systemctl start junos_exporter
```
5. (optional) Tune as needed

## Config file
The config should be located in `/etc/junos_exporter/junos_exporter.yaml`. An example that you can copy is locaed in `junos_exporter.example.yaml`. It should look something like this:
```yaml
---
default:
  auth:
    method: password
    username: username
    password: password
  metrics:
    - interface
    - virtual_chassis
    - routing_engine
    - environment
    - storage
```

The top level element(s) defines the name of the module you are creating. That is to say, you can creat many modules to meet varrying authentication and metric collection needs on your network. Each module must contain two sub elements:

The `auth` section specifies how to authenticate to the device. `method` can be either `password` or `ssh_key` (not yet implemented). With `password`, supply the `username` and `password` for a user that has rights on the device to login and run "show" rpc's.

The `metrics` section list all of the metric types that this module will collect. Each one is described below:
- `interface`: Per interface up/down, input/output bps, input/output bytes, input/output errors, carrier transitions. RPC's:
  - `get_interface_information(extensive=True)`
- `virtual_chassis`: Virtual Chassis health. State of each memeber, and Virtual Chassis Ports. RPC's:
  - `get_virtual_chassis_information()`
  - `get_virtual_chassis_port_information()`
- `routing_engine`: Per routing engine stats. CPU usage, memory usage, temperatures, up time, start time. RPC's:
  - `get_route_engine_information()`
- `environment`: Chassis environmental component status. Measured as "OK"/"Not OK". Fans, power suplies, FPCs, temperatures. RPC's:
  - `get_environment_information()`
- `storage`: Filesystem status. Per volume usage. RPC's:
  - `get_system_storage()`
- `bgp`: BGP peer status. Peer count, per peer state, last state, options (holdtime, preference), flap count, active prefix count, received prefix count, accepted prefix count, suppressed prefix count, advertised prefix count, last received count, last sent count,
last checked count, input/output messages, input/output updates, input/output refreshes, input/output octets, error sent count, error received count. RPC's:
  - `get_bgp_neighbor_information()`

## Tuning
The app is designed to be a lightweight wsgi service running under gunicorn as a set of eventlet workers, all behind nginx. Becasue of the nature of this application, we do some things that would not normall be done in your average gunicorn deployment.

The workers are set to reboot after 10 requests. This is meant to combat cases where devices are unreachable or otherwise take a long time to respond. We try to reap works often to keep them from all getting hung at once.

By default the app ships with 12 workers enabled. This has been load tested to scraping about 100 devices concurently, so YMMV on that, but generally this number can safely be 2 to 3 times the number of cores aviable. Start small and work your up with this number as gunicorn has an upper bound of what it can realistically handle.

All of these settings can be found in the command for the web service in the `docker-compose.yaml` file.