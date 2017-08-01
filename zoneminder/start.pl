#!/usr/bin/perl

use DBI;

# Read the config
open my $fh, '<', '/etc/zm.conf' or die;
my %config;
while (my $data = <$fh>) {
    chomp($data);
    my ($key, $val) = split /=/, $data;
    $config{$key} = $val;
}
close $fh;

# Wait for the mysql container to be up and running
while (1) {
    my $dbh = DBI->connect("DBI:mysql:database=$config{'ZM_DB_NAME'};host=$config{'ZM_DB_HOST'}", $config{'ZM_DB_USER'}, $config{'ZM_DB_PASS'}, {PrintError=>0});
    last if defined $dbh;
    sleep 1;
}

# Start the php-fpm interface
print("Starting Apache\n");
system('/etc/init.d/apache2', 'start');

# Start the zoneminder daemons
print("Starting Zoneminder\n");
system('/etc/init.d/zoneminder', 'start');


$SIG{INT}  = \&signal_handler;
$SIG{TERM} = \&signal_handler;
sub signal_handler {
    print("Stopping Apache\n");
    system('/etc/init.d/apache2', 'stop');
    print("Stopping Zoneminder\n");
    system('/etc/init.d/zoneminder', 'stop');
    die "Caught a signal $!\n";
}

# This process can't exit, sleep loop here
print("Forever Loop\n");
while (1) {
    sleep 3600;
}

