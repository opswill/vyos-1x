#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
import os
import ipaddress
import jinja2
import socket
import struct
import netifaces

from vyos.config import Config
from vyos import ConfigError

config_file = r'/etc/dhcp/dhcpd.conf'
daemon_config_file = r'/etc/default/isc-dhcp-server'

# Please be careful if you edit the template.
config_tmpl = """
### Autogenerated by dhcp_server.py ###

log-facility local7;

{% if hostfile_update %}
on commit {
    set ClientName = pick-first-value(host-decl-name, option fqdn.hostname, option host-name);
    set ClientIp = binary-to-ascii(10, 8, ".", leased-address);
    set ClientMac = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
    set ClientDomain = pick-first-value(config-option domain-name, "..YYZ!");
    execute("/usr/libexec/vyos/system/on-dhcp-event.sh", "commit", ClientName, ClientIp, ClientMac, ClientDomain);
}

on release {
    set ClientName = pick-first-value(host-decl-name, option fqdn.hostname, option host-name);
    set ClientIp = binary-to-ascii(10, 8, ".",leased-address);
    set ClientMac = binary-to-ascii(16, 8, ":",substring(hardware, 1, 6));
    set ClientDomain = pick-first-value(config-option domain-name, "..YYZ!");
    execute("/usr/libexec/vyos/system/on-dhcp-event.sh", "release", ClientName, ClientIp, ClientMac, ClientDomain);
}

on expiry {
    set ClientName = pick-first-value(host-decl-name, option fqdn.hostname, option host-name);
    set ClientIp = binary-to-ascii(10, 8, ".",leased-address);
    set ClientMac = binary-to-ascii(16, 8, ":",substring(hardware, 1, 6));
    set ClientDomain = pick-first-value(config-option domain-name, "..YYZ!");
    execute("/usr/libexec/vyos/system/on-dhcp-event.sh", "release", ClientName, ClientIp, ClientMac, ClientDomain);
}
{% endif %}
ddns-update-style {% if ddns_enable -%} interim {%- else -%} none {%- endif %};
{% if static_route -%}
option rfc3442-static-route code 121 = array of integer 8;
option windows-static-route code 249 = array of integer 8;
{%- endif %}
{% if static_route -%}
option wpad-url code 252 = text;
{% endif %}

{%- if global_parameters %}
# The following {{ global_parameters | length }} line(s) were added as global-parameters in the CLI and have not been validated
{%- for param in global_parameters %}
{{ param }}
{%- endfor -%}
{%- endif %}

# Failover configuration
{% for network in shared_network %}
{%- if not network.disabled -%}
{%- for subnet in network.subnet %}
{%- if subnet.failover_name -%}
failover peer "{{ subnet.failover_name }}" {
{%- if subnet.failover_status == 'primary' %}
    primary;
    mclt 1800;
    split 128;
{%- elif subnet.failover_status == 'secondary' %}
    secondary;
{%- endif %}
    address {{ subnet.failover_local_addr }};
    port 520;
    peer address {{ subnet.failover_peer_addr }};
    peer port 520;
    max-response-delay 30;
    max-unacked-updates 10;
    load balance max seconds 3;
}
{% endif -%}
{% endfor -%}
{% endif -%}
{% endfor %}

# Shared network configrations
{% for network in shared_network %}
{%- if not network.disabled -%}
shared-network {{ network.name }} {
    {% if network.authoritative %}authoritative;{% endif %}
    {%- if network.network_parameters %}
    # The following {{ network.network_parameters | length }} line(s) were added as shared-network-parameters in the CLI and have not been validated
    {%- for param in network.network_parameters %}
    {{ param }}
    {%- endfor -%}
    {%- endif %}
    {%- for subnet in network.subnet %}
    subnet {{ subnet.address }} netmask {{ subnet.netmask }} {
        {%- if subnet.dns_server %}
        option domain-name-servers {{ subnet.dns_server | join(', ') }};
        {%- endif %}
        {%- if subnet.domain_search %}
        option domain-search {{ subnet.domain_search | join(', ') }};
        {%- endif %}
        {%- if subnet.ntp_server %}
        option ntp-servers {{ subnet.ntp_server | join(', ') }};
        {%- endif %}
        {%- if subnet.pop_server %}
        option pop-server {{ subnet.pop_server | join(', ') }};
        {%- endif %}
        {%- if subnet.smtp_server %}
        option smtp-server {{ subnet.smtp_server | join(', ') }};
        {%- endif %}
        {%- if subnet.time_server %}
        option time-servers {{ subnet.time_server | join(', ') }};
        {%- endif %}
        {%- if subnet.wins_server %}
        option netbios-name-servers {{ subnet.wins_server | join(', ') }};
        {%- endif %}
        {%- if subnet.static_route %}
        option rfc3442-static-route {{ subnet.static_route }};
        option windows-static-route {{ subnet.static_route }};
        {%- endif %}
        {%- if subnet.ip_forwarding %}
        option ip-forwarding true;
        {%- endif -%}
        {%- if subnet.default_router %}
        option routers {{ subnet.default_router }};
        {%- endif -%}
        {%- if subnet.server_identifier %}
        option dhcp-server-identifier {{ subnet.server_identifier }};
        {%- endif -%}
        {%- if subnet.domain_name %}
        option domain-name "{{ subnet.domain_name }}";
        {%- endif -%}
        {%- if subnet.tftp_server %}
        option tftp-server-name "{{ subnet.tftp_server }}";
        {%- endif -%}
        {%- if subnet.bootfile_name %}
        option bootfile-name "{{ subnet.bootfile_name }}";
        filename "{{ subnet.bootfile_name }}";
        {%- endif -%}
        {%- if subnet.bootfile_server %}
        next-server {{ subnet.bootfile_server }};
        {%- endif -%}
        {%- if subnet.time_offset %}
        option time-offset {{ subnet.time_offset }};
        {%- endif -%}
        {%- if subnet.wpad_url %}
        option wpad-url "{{ subnet.wpad_url }}";
        {%- endif -%}
        {%- if subnet.client_prefix_length %}
        option subnet-mask {{ subnet.client_prefix_length }};
        {%- endif -%}
        {% if subnet.lease %}
        default-lease-time {{ subnet.lease }};
        max-lease-time {{ subnet.lease }};
        {%- endif -%}
        {%- for host in subnet.static_mapping %}
        {% if not host.disabled -%}
        host {{ network.name }}_{{ host.name }} {
            fixed-address {{ host.ip_address }};
            hardware ethernet {{ host.mac_address }};
            {%- if host.static_parameters %}
            # The following {{ host.static_parameters | length }} line(s) were added as static-mapping-parameters in the CLI and have not been validated
            {%- for param in host.static_parameters %}
            {{ param }}
            {%- endfor -%}
            {%- endif %}
        }
        {%- endif %}
        {%- endfor %}
        {%- for range in subnet.range %}
        range {{ range.start }} {{ range.stop }};
        {%- endfor %}
    }
    {%- endfor %}
    on commit { set shared-networkname = "{{ network.name }}"; }
}
{%- endif %}
{% endfor %}
"""

daemon_tmpl = """
### Autogenerated by dhcp_server.py ###

# sourced by /etc/init.d/isc-dhcp-server

# Path to dhcpd's config file (default: /etc/dhcp/dhcpd.conf).
DHCPD_CONF=/etc/dhcp/dhcpd.conf

# Path to dhcpd's PID file (default: /var/run/dhcpd.pid).
DHCPD_PID=/var/run/dhcpd.pid

# Additional options to start dhcpd with.
#       Don't use options -cf or -pf here; use DHCPD_CONF/ DHCPD_PID instead
OPTIONS="-lf /config/dhcpd.leases"

# On what interfaces should the DHCP server (dhcpd) serve DHCP requests?
#       Separate multiple interfaces with spaces, e.g. "eth0 eth1".
INTERFACES=""
"""

default_config_data = {
    'disabled': False,
    'ddns_enable': False,
    'global_parameters': [],
    'hostfile_update': False,
    'static_route': False,
    'wpad': False,
    'shared_network': [],
}

def get_config():
    dhcp = default_config_data
    conf = Config()
    if not conf.exists('service dhcp-server'):
        return None
    else:
        conf.set_level('service dhcp-server')

    # check for global disable of DHCP service
    if conf.exists('disable'):
        dhcp['disabled'] = True

    # check for global dynamic DNS upste
    if conf.exists('dynamic-dns-update'):
        dhcp['ddns_enable'] = True

    # HACKS AND TRICKS
    #
    # check for global 'raw' ISC DHCP parameters configured by users
    # actually this is a bad idea in general to pass raw parameters from any user
    if conf.exists('global-parameters'):
        dhcp['global_parameters'] = conf.return_values('global-parameters')

    # check for global DHCP server updating /etc/host per lease
    if conf.exists('hostfile-update'):
        dhcp['hostfile_update'] = True

    # check for multiple, shared networks served with DHCP addresses
    if conf.exists('shared-network-name'):
        for network in conf.list_nodes('shared-network-name'):
            conf.set_level('service dhcp-server shared-network-name {0}'.format(network))
            config = {
                'name': network,
                'authoritative': False,
                'description': '',
                'disabled': False,
                'network_parameters': [],
                'subnet': []
            }
            # check if DHCP server should be authoritative on this network
            if conf.exists('authoritative'):
                config['authoritative'] = True

            # A description for this given network
            if conf.exists('description'):
                config['description'] = conf.return_value('description')

            # If disabled, the shared-network configuration becomes inactive in
            # the running DHCP server instance
            if conf.exists('disable'):
                config['disabled'] = True

            # HACKS AND TRICKS
            #
            # check for 'raw' ISC DHCP parameters configured by users
            # actually this is a bad idea in general to pass raw parameters
            # from any user
            #
            # deprecate this and issue a warning like we do for DNS forwarding?
            if conf.exists('shared-network-parameters'):
                config['network_parameters'] = conf.return_values('shared-network-parameters')

            # check for multiple subnet configurations in a shared network
            # config segment
            if conf.exists('subnet'):
                for net in conf.list_nodes('subnet'):
                    conf.set_level('service dhcp-server shared-network-name {0} subnet {1}'.format(network, net))
                    subnet = {
                        'network': net,
                        'address': str(ipaddress.ip_network(net).network_address),
                        'netmask': str(ipaddress.ip_network(net).netmask),
                        'bootfile_name': '',
                        'bootfile_server': '',
                        'client_prefix_length': '',
                        'default_router': '',
                        'dns_server': [],
                        'domain_name': '',
                        'domain_search': [],
                        'exclude': [],
                        'failover_local_addr': '',
                        'failover_name': '',
                        'failover_peer_addr': '',
                        'failover_status': '',
                        'ip_forwarding': False,
                        'lease': '86400',
                        'ntp_server': [],
                        'pop_server': [],
                        'server_identifier': '',
                        'smtp_server': [],
                        'range': [],
                        'static_mapping': [],
                        'static_subnet': '',
                        'static_router': '',
                        'static_route': '',
                        'subnet_parameters': [],
                        'tftp_server': '',
                        'time_offset': '',
                        'time_server': [],
                        'wins_server': [],
                        'wpad_url': ''
                    }

                    # Used to identify a bootstrap file
                    if conf.exists('bootfile-name'):
                        subnet['bootfile_name'] = conf.return_value('bootfile-name')

                    # Specify host address of the server from which the initial boot file
                    # (specified above) is to be loaded. Should be a numeric IP address or
                    # domain name.
                    if conf.exists('bootfile-server'):
                        subnet['bootfile_server'] = conf.return_value('bootfile-server')

                    # The subnet mask option specifies the client's subnet mask as per RFC 950. If no subnet
                    # mask option is provided anywhere in scope, as a last resort dhcpd will use the subnet
                    # mask from the subnet declaration for the network on which an address is being assigned.
                    if conf.exists('client-prefix-length'):
                        # snippet borrowed from https://stackoverflow.com/questions/33750233/convert-cidr-to-subnet-mask-in-python
                        host_bits = 32 - int(conf.return_value('client-prefix-length'))
                        subnet['client_prefix_length'] = socket.inet_ntoa(struct.pack('!I', (1 << 32) - (1 << host_bits)))

                    # Default router IP address on the client's subnet
                    if conf.exists('default-router'):
                        subnet['default_router'] = conf.return_value('default-router')

                    # Specifies a list of Domain Name System (STD 13, RFC 1035) name servers available to
                    # the client. Servers should be listed in order of preference.
                    if conf.exists('dns-server'):
                        subnet['dns_server'] = conf.return_values('dns-server')

                    # Option specifies the domain name that client should use when resolving hostnames
                    # via the Domain Name System.
                    if conf.exists('domain-name'):
                        subnet['domain_name'] = conf.return_value('domain-name')

                    # The domain-search option specifies a 'search list' of Domain Names to be used
                    # by the client to locate not-fully-qualified domain names.
                    if conf.exists('domain-search'):
                        for domain in conf.return_values('domain-search'):
                            subnet['domain_search'].append('"' + domain + '"')

                    # IP address (local) for failover peer to connect
                    if conf.exists('failover local-address'):
                        subnet['failover_local_addr'] = conf.return_value('failover local-address')

                    # DHCP failover peer name
                    if conf.exists('failover name'):
                        subnet['failover_name'] = conf.return_value('failover name')

                    # IP address (remote) of failover peer
                    if conf.exists('failover peer-address'):
                        subnet['failover_peer_addr'] = conf.return_value('failover peer-address')

                    # DHCP failover peer status (primary|secondary)
                    if conf.exists('failover status'):
                        subnet['failover_status'] = conf.return_value('failover status')

                    # Option specifies whether the client should configure its IP layer for packet
                    # forwarding
                    if conf.exists('ip-forwarding'):
                        subnet['ip_forwarding'] = True

                    # Time should be the length in seconds that will be assigned to a lease if the
                    # client requesting the lease does not ask for a specific expiration time
                    if conf.exists('lease'):
                        subnet['lease'] = conf.return_value('lease')

                    # Specifies a list of IP addresses indicating NTP (RFC 5905) servers available
                    # to the client.
                    if conf.exists('ntp-server'):
                        subnet['ntp_server'] = conf.return_values('ntp-server')

                    # POP3 server option specifies a list of POP3 servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('pop-server'):
                        subnet['pop_server'] = conf.return_values('pop-server')

                    # DHCP servers include this option in the DHCPOFFER in order to allow the client
                    # to distinguish between lease offers. DHCP clients use the contents of the
                    # 'server identifier' field as the destination address for any DHCP messages
                    # unicast to the DHCP server
                    if conf.exists('server-identifier'):
                        subnet['server_identifier'] = conf.return_value('server-identifier')

                    # SMTP server option specifies a list of SMTP servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('smtp-server'):
                        subnet['smtp_server'] = conf.return_values('smtp-server')

                    # For any subnet on which addresses will be assigned dynamically, there must be at
                    # least one range statement. The range statement gives the lowest and highest IP
                    # addresses in a range. All IP addresses in the range should be in the subnet in
                    # which the range statement is declared.
                    if conf.exists('range'):
                        for range in conf.list_nodes('range'):
                            range = {
                                'start': conf.return_value('range {0} start'.format(range)),
                                'stop':  conf.return_value('range {0} stop'.format(range))
                            }
                            subnet['range'].append(range)

                    # IP address that needs to be excluded from DHCP lease range
                    if conf.exists('exclude'):
                        # We have no need to store the exclude addresses. Exclude addresses
                        # are recalculated into several ranges
                        exclude = []
                        subnet['exclude'] = conf.return_values('exclude')
                        for addr in subnet['exclude']:
                            exclude.append(ipaddress.ip_address(addr))

                        # sort excluded IP addresses ascending
                        exclude = sorted(exclude)

                        # calculate multipe ranges based on the excluded IP addresses
                        output = []
                        for range in subnet['range']:
                            range_start = range['start']
                            range_stop = range['stop']

                            for i in exclude:
                                # Excluded IP address must be in out specified range
                                if (i >= ipaddress.ip_address(range_start)) and (i <= ipaddress.ip_address(range_stop)):
                                    # Build up new IP address range ending one IP address before
                                    # our exclude address
                                    range = {
                                        'start': str(range_start),
                                        'stop': str(i - 1)
                                    }
                                    # Our next IP address range will start one address after
                                    # our exclude address
                                    range_start = i + 1
                                    output.append(range)

                                    # Take care of last IP address range spanning from the last exclude
                                    # address (+1) to the end of the initial configured range
                                    if i is exclude[-1]:
                                        last = {
                                            'start': str(i + 1),
                                            'stop': str(range_stop)
                                        }
                                        output.append(last)
                                else:
                                    # IP address not inside search range, take range is it is
                                    output.append(range)

                        # We successfully build up a new list containing several IP address
                        # ranges, replace IP address range in our dictionary
                        subnet['range'] = output

                    # Static DHCP leases
                    if conf.exists('static-mapping'):
                        for mapping in conf.list_nodes('static-mapping'):
                            conf.set_level('service dhcp-server shared-network-name {0} subnet {1} static-mapping {2}'.format(network, net, mapping))
                            mapping = {
                                'name': mapping,
                                'disabled': False,
                                'ip_address': '',
                                'mac_address': '',
                                'static_parameters': []
                            }

                            # This static lease is disabled
                            if conf.exists('disable'):
                                mapping['disabled'] = True

                            # IP address used for this DHCP client
                            if conf.exists('ip-address'):
                                mapping['ip_address'] = conf.return_value('ip-address')

                            # MAC address of requesting DHCP client
                            if conf.exists('mac-address'):
                                mapping['mac_address'] = conf.return_value('mac-address')

                            # HACKS AND TRICKS
                            #
                            # check for 'raw' ISC DHCP parameters configured by users
                            # actually this is a bad idea in general to pass raw parameters
                            # from any user
                            #
                            # deprecate this and issue a warning like we do for DNS forwarding?
                            if conf.exists('static-mapping-parameters'):
                                mapping['static_parameters'] = conf.return_values('static-mapping-parameters')

                            # append static-mapping configuration to subnet list
                            subnet['static_mapping'].append(mapping)

                    # Reset config level to matching hirachy
                    conf.set_level('service dhcp-server shared-network-name {0} subnet {1}'.format(network, net))

                    # This option specifies a list of static routes that the client should install in its routing
                    # cache. If multiple routes to the same destination are specified, they are listed in descending
                    # order of priority.
                    if conf.exists('static-route destination-subnet'):
                        subnet['static_subnet'] = conf.return_value('static-route destination-subnet')
                        # Required for global config section
                        dhcp['static_route'] = True

                    if conf.exists('static-route router'):
                        subnet['static_router'] = conf.return_value('static-route router')

                    if subnet['static_router'] and subnet['static_subnet']:
                        # https://ercpe.de/blog/pushing-static-routes-with-isc-dhcp-server
                        # Option format is:
                        # <netmask>, <network-byte1>, <network-byte2>, <network-byte3>, <router-byte1>, <router-byte2>, <router-byte3>
                        # where bytes with the value 0 are omitted.
                        net = ipaddress.ip_network(subnet['static_subnet'])
                        # add netmask
                        string = str(net.prefixlen) + ','
                        # add network bytes
                        bytes = str(net.network_address).split('.')
                        for b in bytes:
                            if b != '0':
                                string += b + ','

                        # add router bytes
                        bytes = subnet['static_router'].split('.')
                        for b in bytes:
                            if b != '0':
                                string += b
                                if b is not bytes[-1]:
                                    string += ','

                        subnet['static_route'] = string

                    # HACKS AND TRICKS
                    #
                    # check for 'raw' ISC DHCP parameters configured by users
                    # actually this is a bad idea in general to pass raw parameters
                    # from any user
                    #
                    # deprecate this and issue a warning like we do for DNS forwarding?
                    if conf.exists('subnet-parameters'):
                        config['subnet_parameters'] = conf.return_values('subnet-parameters')

                    # This option is used to identify a TFTP server and, if supported by the client, should have
                    # the same effect as the server-name declaration. BOOTP clients are unlikely to support this
                    # option. Some DHCP clients will support it, and others actually require it.
                    if conf.exists('tftp-server-name'):
                        subnet['tftp_server'] = conf.return_value('tftp-server-name')

                    # The time-offset option specifies the offset of the client’s subnet in seconds from
                    # Coordinated Universal Time (UTC).
                    if conf.exists('time-offset'):
                        subnet['time_offset'] = conf.return_value('time-offset')

                    # The time-server option specifies a list of RFC 868 time servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('time-server'):
                        subnet['time_server'] = conf.return_values('time-server')

                    # The NetBIOS name server (NBNS) option specifies a list of RFC 1001/1002 NBNS name servers
                    # listed in order of preference. NetBIOS Name Service is currently more commonly referred to
                    # as WINS. WINS servers can be specified using the netbios-name-servers option.
                    if conf.exists('wins-server'):
                        subnet['wins_server'] = conf.return_values('wins-server')

                    # URL for Web Proxy Autodiscovery Protocol
                    if conf.exists('wpad-url'):
                        subnet['wpad_url'] = conf.return_value('wpad-url')
                        # Required for global config section
                        dhcp['wpad'] = True

                    # append subnet configuration to shared network subnet list
                    config['subnet'].append(subnet)

            # append shared network configuration to config dictionary
            dhcp['shared_network'].append(config)

    return dhcp

def verify(dhcp):
    if (dhcp is None) or (dhcp['disabled'] is True):
        return None

    # If DHCP is enabled we need one share-network
    if len(dhcp['shared_network']) == 0:
        raise ConfigError('No DHCP shared networks configured. At least one DHCP shared network must be configured.')

    # A shared-network requires a subnet definition
    for network in dhcp['shared_network']:
        if len(network['subnet']) == 0:
            raise ConfigError('No DHCP lease subnets configured for "{0}". At least one DHCP lease subnet must be configured for each shared network.'.format(network['name']))

    # Inspect our subnet configuration
    failover_names = []
    listen_ok = False
    subnets = []
    for network in dhcp['shared_network']:
        for subnet in network['subnet']:
            # Subnet static route declaration requires destination and router
            if subnet['static_subnet'] or subnet['static_router']:
                if not (subnet['static_subnet'] and subnet['static_router']):
                    raise ConfigError('Please specify the missing DHCP static-route parameter: destination-subnet | router')

            # Failover requires all 4 parameters set
            if subnet['failover_local_addr'] or subnet['failover_peer_addr'] or subnet['failover_name'] or subnet['failover_status']:
                if not (subnet['failover_local_addr'] and subnet['failover_peer_addr'] and subnet['failover_name'] and subnet['failover_status']):
                    raise ConfigError('Please set one or more of the missing DHCP failover parameters: local-address | peer-address | name | status')

                # Failover names must be uniquie
                if subnet['failover_name'] in failover_names:
                    raise ConfigError('Failover names should be unique: "{0}" has already been configured.'.format(subnet['failover_name']))
                else:
                    failover_names.append(subnet['failover_name'])

                # Failover requires start/stop ranges for pool
                if (len(subnet['range']) == 0):
                    raise ConfigError('Atleast one start-stop range must be configured for $subnet to set up DHCP failover.')

            # Check if DHCP address range is inside configured subnet declaration
            range_start = []
            range_stop = []
            for range in subnet['range']:
                # DHCP stop IP required after start IP
                if range['start'] and not range['stop']:
                    raise ConfigError('DHCP range stop IP not defined for range start IP "{0}".'.format(range['start']))

                # Start address must be inside network
                if not ipaddress.ip_address(range['start']) in ipaddress.ip_network(subnet['network']):
                    raise ConfigError('DHCP range start IP "{0}" is not in subnet "{1}" specified in network "{2}."'.format(range['start'], subnet['network'], network['name']))

                # Stop address must be inside network
                if not ipaddress.ip_address(range['stop']) in ipaddress.ip_network(subnet['network']):
                    raise ConfigError('DHCP range stop IP "{0}" is not in  subnet "{1}" specified in network "{2}."'.format(range['stop'], subnet['network'], network['name']))

                # Stop address must be greater or equal to start address
                if not ipaddress.ip_address(range['stop']) >= ipaddress.ip_address(range['start']):
                    raise ConfigError('DHCP range stop IP "{0}" should be an address greater or equal to the start address "{1}".'.format(range['stop'], range['start']))

                # Range start address must be unique
                if range['start'] in range_start:
                    raise ConfigError('Conflicting DHCP lease ranges: Pool start address "{0}" defined multipe times'.format(range['start']))
                else:
                    range_start.append(range['start'])

                # Range stop address must be unique
                if range['stop'] in range_stop:
                    raise ConfigError('Conflicting DHCP lease ranges: Pool stop address "{0}" defined multipe times'.format(range['stop']))
                else:
                    range_stop.append(range['stop'])

            # Exclude addresses must be in bound
            for exclude in subnet['exclude']:
                if not ipaddress.ip_address(exclude) in ipaddress.ip_network(subnet['network']):
                    raise ConfigError('Exclude IP "{0}" is outside of the DHCP lease network "{1}" under shared network "{2}".'.format(exclude, subnet['network'], network['name']))

            # At least one DHCP address range or static-mapping required
            active_mapping = False
            if (len(subnet['range']) == 0):
                for mapping in subnet['static_mapping']:
                    # we need at least one active mapping
                    if (not active_mapping) and (not mapping['disable']):
                        active_mapping = True
            else:
                active_mapping = True

            if not active_mapping:
                raise ConfigError('No DHCP address range or active static-mapping set for subnet "{0}".'.format(subnet['network']))

            # Static IP address mappings require both an IP address and MAC address
            for mapping in subnet['static_mapping']:
                # Static IP address must be configured
                if not mapping['ip_address']:
                    raise ConfigError('No static lease IP address specified for static mapping "{0}" under shared network name "{1}".'.format(mapping['name'], network['name']))

                # Static IP address must be in bound
                if not ipaddress.ip_address(mapping['ip_address']) in ipaddress.ip_network(subnet['network']):
                    raise ConfigError('Static DHCP lease IP "{0}" under static mapping "{1}" in shared network "{2}" is outside DHCP lease network "{3}".'.format(mapping['ip_address'], mapping['name'], network['name'], subnet['network'], ))

                # Static mapping requires MAC address
                if not mapping['mac_address']:
                     raise ConfigError('No static lease MAC address specified for static mapping "{0}" under shared network name "{1}".'.format(mapping['name'], network['name']))

            #
            # There must be one subnet connected to a real interface
            #
            for interface in netifaces.interfaces():
                # Retrieve IP address of network interface
                ip = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
                if ipaddress.ip_address(ip) in ipaddress.ip_network(subnet['network']):
                    listen_ok = True

            #
            # Subnets must be non overlapping
            #
            if subnet['network'] in subnets:
                raise ConfigError('Subnets must be unique! "{0}" defined multiple times.'.format(subnet))
            else:
                subnets.append(subnet['network'])

            #
            # Check for overlapping subnets
            #
            net = ipaddress.ip_network(subnet['network'])
            for n in subnets:
                net2 = ipaddress.ip_network(n)
                if (net.compare_networks(net2) != 0):
                    if net.overlaps(net2):
                        raise ConfigError('Conflicting subnet ranges: "{0}" overlaps "{1}"'.format(net, net2))

    if not listen_ok:
        raise ConfigError('None of the DHCP lease subnets are inside any configured subnet on broadcast interfaces. At least one lease subnet must be set such that DHCP server listens on a one broadcast interface')

    return None

def generate(dhcp):
    if dhcp is None:
        return None

    if dhcp['disabled'] is True:
        print('Warning: DHCP server will be deactivated because it is disabled')
        return None

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(dhcp)
    with open(config_file, 'w') as f:
        f.write(config_text)

    tmpl = jinja2.Template(daemon_tmpl)
    config_text = tmpl.render(dhcp)
    with open(daemon_config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(dhcp):
    if (dhcp is None) or dhcp['disabled']:
        # DHCP server is removed in the commit
        os.system('sudo systemctl stop isc-dhcp-server.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
        if os.path.exists(daemon_config_file):
            os.unlink(daemon_config_file)
    else:
        os.system('sudo systemctl restart isc-dhcp-server.service')

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
