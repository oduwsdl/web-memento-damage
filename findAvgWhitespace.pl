#!/usr/bin/perl
#

#liveBackground.csv  localBackground.csv  nocssBackground.csv
open(FILE, "./liveBackground.csv") or die ("Cannot find liveBackground\n\n");
my @liveLines = <FILE>;      #get first line off
close(FILE);

open(FILE, "./localBackground.csv") or die ("Cannot find localBackground\n\n");
my @localLines = <FILE>;      #get first line off
close(FILE);

open(FILE, "./nocssBackground.csv") or die ("Cannot find nocssBackground\n\n");
my @nocssLines = <FILE>;      #get first line off
close(FILE);

my $liveLeft = 0;
my $localLeft = 0;
my $nocssLeft = 0;

my $liveMid = 0;
my $localMid = 0;
my $nocssMid = 0;

my $liveRight = 0;
my $localRight = 0;
my $nocssRight = 0;

my $counter = 0;
for my $l (@liveLines)
{
	$l = trim($l);

	my @arr = split(/, /, $l);
	$liveLeft += trim($arr[1]);
	$liveMid += trim($arr[2]);
	$liveRight += trim($arr[3]);

	$counter++;
}

if($counter == 0)
{
	$counter = 1;
}

$liveLeft = $liveLeft/$counter;
$liveMid = $liveMid/$counter;
$liveRight = $liveRight/$counter;

print "$#localLines local ones\n";
my $counter = 0;
for my $l (@localLines)
{
	$l = trim($l);

	#print "Line $l\n";

	my @arr = split(/, /, $l);
	$localLeft += trim($arr[1]);
	$localMid += trim($arr[2]);
	$localRight += trim($arr[3]);

	$counter++;
}

if($counter == 0)
{
	$counter = 1;
}

$localLeft = $localLeft/$counter;
$localMid = $localMid/$counter;
$localRight = $localRight/$counter;


my $counter = 0;
for my $l (@nocssLines)
{
	$l = trim($l);

	my @arr = split(/, /, $l);
	$nocssLeft += trim($arr[1]);
	$nocssMid += trim($arr[2]);
	$nocssRight += trim($arr[3]);

	$counter++;
}

if($counter == 0)
{
	$counter = 1;
}

$nocssLeft = $nocssLeft/$counter;
$nocssMid = $nocssMid/$counter;
$nocssRight = $nocssRight/$counter;


print "Live: $liveLeft, $liveMid, $liveRight\n";
print "Local: $localLeft, $localMid, $localRight\n";
print "No CSS: $nocssLeft, $nocssMid, $nocssRight\n";



sub trim($)
{
        my $string = shift;
        $string =~ s/^\s+//;
        $string =~ s/\s+$//;
        return $string;
}
