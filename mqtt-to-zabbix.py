#!/usr/bin/env python3
try:
    import paho.mqtt.client as mqtt
except:
    print("please install paho-mqtt (e.g. pip3 install --user paho-mqtt)")
    raise
import os
import sys
import argparse
import signal
import multiprocessing
import subprocess
import json

filename='/tmp/mqtt-to-zabbix.{}'.format(os.getpid())

def send_dump_to_zabbix(prog,q):
    while True:
        metrics=q.get()
        with open(filename,mode="w") as target:
            for k,v in metrics.items():
                splitted=k.split("/")
                host=splitted[0]
                if "devices" in splitted:
                    offset=splitted.index("devices")+1
                    device_id=splitted[offset].split("_",1)
                    k=device_id[0]+'['+'/'.join(splitted[offset:])+']'
                else:
                    k='/'.join(splitted[1:])
                print("{} {} {}".format(json.dumps(host),json.dumps(k),json.dumps(v)),file=target)
        subprocess.call(prog)
        q.task_done()

def parse_data_for_lld(mqtt_data):
    lld={}
    lld_skip={}
    for k in mqtt_data:
        splitted=k.split("/")
        host=splitted[0]
        if "devices" in splitted:
            offset=splitted.index("devices")+1
            device_id=splitted[offset].split("_",1)
            if not "controls" in splitted[offset+1]:
                continue
            elif len(device_id) > 1:
                pass
            elif "wb-w1" in splitted[offset]:
                offset+=2
            else:
                continue
            if splitted[offset] in lld_skip:
                continue
            lld_skip[splitted[offset]]=True
            name_macro="N_"+str.upper(splitted[offset].replace("-","_"))
            lld_info={"{#DEVICE}":splitted[offset],"{#MACRO}":name_macro}
            k=host+'/'+device_id[0]+'.lld'
            if not k in lld:
                lld[k]=[lld_info]
            else:
                lld[k].append(lld_info)
    for k in lld:
        lld[k]=json.dumps(lld[k])
    return lld

def copy_every(seconds,mqtt_data,q,only_new):
    def trapper(signum, frame):
        if only_new:
            q.put(mqtt_data.copy())
            mqtt_data.clear()
        else:
            q.put(mqtt_data)
        signal.alarm(seconds)
    signal.signal(signal.SIGALRM, trapper)
    signal.alarm(seconds)

def make_lld(seconds,mqtt_data,q,client):
    def trapper(signum, frame):
        q.put(parse_data_for_lld(mqtt_data))
        client.disconnect()
    signal.signal(signal.SIGALRM, trapper)
    signal.alarm(seconds)

def on_connect(client,userdata,flags,rc):
    """
    rc:
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

def publish(client,topic,payload=None,qos=0,retain=False):
    return client.publish(topic,payload,qos,retain)

def on_message(client,userdata,msg):
    topic=userdata['args'].zabbix_sender_source+msg.topic
    if not userdata['args'].every or ( userdata['args'].instant and userdata['args'].instant in msg.topic ):
        userdata['q'].put({topic:msg.payload.decode().strip()})
    else:
        userdata['mqtt_data'][topic]=msg.payload.decode().strip()

def get_parser():
    parser=argparse.ArgumentParser(description="Wirenboard MQTT-to-Zabbix gateway", add_help=False)
    parser.add_argument("--help",action='help')
    parser.add_argument("-h","--mqtt-host",help="MQTT host",default="localhost")
    parser.add_argument("-p","--mqtt-port",type=int,help="MQTT port",default=1883)
    parser.add_argument("-t","--mqtt-topic",help="MQTT topic to subscribe",default="/#")
    parser.add_argument("--mqtt-keepalive",type=int,help="MQTT keepalive",default=60)
    parser.add_argument("--mqtt-tls",help="MQTT keepalive",default=False,action='store_true')
    parser.add_argument("-P","--mqtt-password",help="MQTT password")
    parser.add_argument("-u","--mqtt-login",help="MQTT login")
    parser.add_argument("-c","--zabbix-sender-config",help="path to zabbix_sender config",default="/etc/zabbix/zabbix_agentd.conf")
    parser.add_argument("-s","--zabbix-sender-source",help="source host for zabbix_sender",default="-")
    parser.add_argument("--every",type=int,help="send data to zabbix ever n seconds",default=10)
    parser.add_argument("--only-new",help="send only fresh data",default=False,action='store_true')
    parser.add_argument("--instant",help="send this topics immediately")
    parser.add_argument("--lld",help="start lld-discovery",action='store_true')
    parser.add_argument("--lld-null",action="append",help="Emit empty lld for device")
    return parser

def get_client(userdata,on_connect,on_message):
    client=mqtt.Client(clean_session=True)
    if userdata['args'].mqtt_login:
        client.username_pw_set(userdata['args'].mqtt_login, password=userdata['args'].mqtt_password)
    if userdata['args'].mqtt_tls:
        client.tls_set()
    client.user_data_set(userdata)
    client.on_message=on_message
    client.on_connect=on_connect
    client.connect(userdata['args'].mqtt_host,userdata['args'].mqtt_port,keepalive=userdata['args'].mqtt_keepalive)
    return client

def letsgo():
    args=get_parser().parse_args()
    q=multiprocessing.JoinableQueue()
    mqtt_data={}
    userdata={"args":args,"mqtt_data":mqtt_data,"q":q}
    zabbix_sender_options=("zabbix_sender","--config",args.zabbix_sender_config,"-i",filename)
    client=get_client(userdata,on_connect,on_message)
    p=multiprocessing.Process(target=send_dump_to_zabbix,args=(zabbix_sender_options,q))
    p.start()
    if args.lld_null:
        args.instant=None
        for k in args.lld_null:
            q.put({args.zabbix_sender_source+'/'+k+'.lld':json.dumps([])})
    elif args.lld:
        args.instant=None
        make_lld(args.every,mqtt_data,q,client)
        client.loop_forever()
    else:
        if args.every:
            copy_every(args.every,mqtt_data,q,args.only_new)
        client.loop_forever()
    q.join()
    p.terminate()

if __name__ == "__main__":
    letsgo()
