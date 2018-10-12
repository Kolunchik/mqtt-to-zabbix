#/usr/bin/env perl
use strict;
use warnings;

my ($FP);
my $infile='/tmp/dump.txt';
my $mode=shift || '--process'; # process / lld / lld-null
my $zabbix_sender="zabbix_sender --config /etc/zabbix/zabbix_agentd.conf";
open ($FP,"<",$infile) or die "Can`t open < $infile!: $!";

if ($mode eq '--process')
{
    while (<$FP>)
    {
        next if /^$/;
        chomp;
        my $offset=2;
        my @topic=split("/|\t");
        my ($host,$id)=split('_',$topic[$offset],2);
        my $payload=$topic[-1];
        $payload=~s/"/\\"/g;
        my $topic_name=join('/',@topic[$offset..$#topic-1]);
        $topic_name=~s/"/\\"/g;
        print qq/- "${host}[${topic_name}]" "${payload}"\n/;
    }
} elsif ($mode eq '--lld') {
    my (%lld,%lld_skip);
    while (<$FP>)
    {
        next if /^$/;
        my $offset=2;
        my @topic=split("/|\t");
        my ($host,$id)=split('_',$topic[$offset],2);
        next if $topic[$offset+1]!~/controls/i;
        if($host=~/wb-w1/)
        {
            $offset+=2;
        } elsif (!$id)
        {
            next;
        }
        next if $lld_skip{$topic[$offset]};
        $lld_skip{$topic[$offset]}=1;
        $lld{$host}=[] unless $lld{$host};
        my $name_macro="N_\U$topic[$offset]";
        $name_macro=~s/-/_/g;
        my $lld_info={"{#DEVICE}"=>$topic[$offset],"{#MACRO}"=>$name_macro};
        push (@{ $lld{$host} },$lld_info);
    }
    eval "use JSON::XS;";
    die $@ if $@;
    my $sleep=int(rand(60));
    print ("#!/usr/bin/env bash\n");
    print ("sleep $sleep\n");
    for my $device(keys %lld)
    {
        print "$zabbix_sender -k $device.lld -o '".encode_json({"data"=>$lld{$device}})."'\n";
    }
} elsif ($mode eq '--lld-null') {
    eval "use JSON::XS;";
    die $@ if $@;
    my $lld=[];
    my $device=shift or die "example: $0 --lld-null wb-w1";
    print "$zabbix_sender -k $device.lld -o '".encode_json({"data"=>$lld})."'\n";
} else {
    die "wat?";
}

close $FP;

1;
