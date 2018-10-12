# mqtt-to-zabbix
Простой шаблон для связи WirenBoard и Zabbix, с применением LLD и макросов

Шаблон предназначен для простой и быстрой настройки мониторинга множества датчиков, подключенных к устройствам WirenBoard или любым другим, которые придерживаются подобной схемы названий топиков в mqtt.

В основном мспользуются штатные шаблоны от WirenBoard. В папке wb-homa-modbus-templates лежат шаблоны для устройств, не имеющих штатных шаблонов - их нужно, при необходимости, положить в /usr/share/wb-homa-modbus/templates/.

*.xml файлы предназначены для импорта в Zabbix (нужна версия не ниже 3.4)

В mqtt-dump-to-zabbix.pl реализация разбора дампа, получаемого на WirenBoard с помощью mqtt-get-dump, на perl (может пригодится для опытов).

Скрипт mqtt-to-zabbix.py использует пакет paho.mqtt.client и хорошо работает под Python 3 на сторонних машинах, подключаясь к mqtt-брокеру (штатному, прямо на WirenBoard или любому другому, например на агрегации).

Скрипт mqtt-to-zabbix-wb.py использует пакет mosquitto, заранее установленный на все WirenBoard и отлично работает прямо на устройстве.

Для отправки все скрипты используют вызов zabbix_sender. Как показала практика, это быстрее и проще.

Файл mqtt-to-zabbix.service - образец юнита для systemd.

Файлы to_wirenboard_crontab.txt и to_wirenboard_monit.txt содержат примеры запуска скриптов на устройствах WirenBoard.

Настройки влажности, температуры, названий датчиков и входов датчиков осуществляются через макросы в шаблоне Zabbix.

Эта схема работает уже много лет на большой инсталляции и показала свою жизнеспособность.
