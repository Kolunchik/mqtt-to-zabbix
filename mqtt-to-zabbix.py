#!/usr/bin/env python
# -*- coding: utf8 -*-
try:
    import paho.mqtt.client as mqtt
except:
    print("please install paho-mqtt (e.g. pip3 install --user paho-mqtt)")
    raise
import subprocess
import sys
import argparse

def on_connect(client, userdata, flags, rc):
    """
    0: Success
    1: Refused – unacceptable protocol version
    2: Refused – identifier rejected
    3: Refused – server unavailable
    4: Refused – bad user name or password (MQTT v3.1 broker only)
    5: Refused – not authorised (MQTT v3.1 broker only)
    """
    print("Connected with result code "+str(rc))
    if rc: sys.exit(rc)
    client.subscribe(userdata['args'].mqtt_topic)

def on_message_nope(client, userdata, msg):
    print(msg.topic+"="+msg.payload.decode().strip())

def on_message_zabbix_send(client, userdata, msg):
    topic=msg.topic.split("/")
    offset=topic.index("devices")+1
    device_id=topic[offset].split("_",1)
    topic="/".join(topic[offset:])
    payload=msg.payload.decode().strip()
    zs=userdata['zabbix_sender']+["-k",device_id[0]+"["+topic+"]","-o",payload]
    subprocess.call(zs)
    print(zs)

def on_message_zabbix_lld(client, userdata, msg):
    topic=msg.topic.split("/")
    offset=topic.index("devices")+1
    device_id=topic[offset].split("_",1)

    if not "controls" in topic[offset+1]:
        return
    elif len(device_id) > 1:
        pass
    elif "wb-w1" in topic[offset]:
        offset+=2
    else:
        return

    if topic[offset] in userdata['lld_skip']:
        return

    userdata['lld_skip'][topic[offset]]=True
    name_macro="N_"+str.upper(topic[offset].replace("-","_"))
    lld_info={"{#DEVICE}":topic[offset],"{#MACRO}":name_macro}
    if not device_id[0] in userdata['lld']:
        userdata['lld'][device_id[0]]=[]
    userdata['lld'][device_id[0]].append(lld_info)

def on_disconnect_zabbix_lld(client, userdata, rc):
    import json
    if 'lld' in userdata:
        for key in userdata['lld']:
            lld={"data":userdata['lld'][key]}
            zs=userdata['zabbix_sender']+["-k",key+".lld","-o",json.dumps(lld)]
            subprocess.call(zs)
            print(zs)

def get_parser():
    parser=argparse.ArgumentParser(description="Wirenboard MQTT-to-Zabbix gateway", add_help=False)
    parser.add_argument("--help",action='help')
    parser.add_argument("-h","--mqtt-host",help="MQTT host",default="localhost")
    parser.add_argument("-p","--mqtt-port",type=int,help="MQTT port",default=1883)
    parser.add_argument("-t","--mqtt-topic",help="MQTT topic to subscribe",default="/devices/#")
    parser.add_argument("--mqtt-keepalive",type=int,help="MQTT keepalive",default=60)
    parser.add_argument("--mqtt-tls",help="MQTT keepalive",default=False,action='store_true')
    parser.add_argument("--mqtt-password",help="MQTT password")
    parser.add_argument("--mqtt-login",help="MQTT login")
    parser.add_argument("-c","--zabbix-sender-config",help="Path to zabbix_sender config",default="/etc/zabbix/zabbix_agentd.conf")
    parser.add_argument("--lld",help="Start lld-discovery",action='store_true')
    parser.add_argument("--lld-duration",type=int,help="Seconds of lld-discovery duration",default=15)
    parser.add_argument("--lld-null",help="Emit empty lld for device")
    return parser

def get_client(args):
    client=mqtt.Client(clean_session=True)
    if args.mqtt_login:
        client.username_pw_set(args.mqtt_login, password=args.mqtt_password)
    if args.mqtt_tls:
        client.tls_set()
    return client

def letsgo():
    args=get_parser().parse_args()
    userdata={"args":args,"lld":{},"lld_skip":{}}
    userdata['zabbix_sender']=["zabbix_sender","--config",args.zabbix_sender_config]
    if args.lld_null:
        userdata['lld'][args.lld_null]=[]
        on_disconnect_zabbix_lld(None,userdata,None)
        sys.exit()
    client=get_client(args)
    client.user_data_set(userdata)
    if args.lld:
        import signal
        def exit_trapper(signum, frame):
            client.disconnect()
        signal.signal(signal.SIGALRM, exit_trapper)
        signal.alarm(args.lld_duration)
        client.on_message=on_message_zabbix_lld
        client.on_disconnect=on_disconnect_zabbix_lld
    else:
        client.on_message=on_message_zabbix_send
    client.on_connect=on_connect
    client.connect(args.mqtt_host,args.mqtt_port,keepalive=args.mqtt_keepalive)
    client.loop_forever()

if __name__ in "__main__":
    letsgo()
