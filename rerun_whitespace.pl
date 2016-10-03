#!/usr/bin/perl
#
# Overall demo of the major PerlMagick methods.
#
use Image::Magick;
use POSIX;
use Color::Rgb;

my $USEVIEWPORT = 1;
my $XLIM = 1024;
my $YLIM = 777;

my($image, $x);

  print "Finding..." . $ARGV[0] . "\n";
  my $bgColor = "#000000";

  print "BG Color: $bgColor\n\n";

($width, $height, $size, $format) = $image->Ping($ARGV[0]);

print "W x H: " . $width . " x " . $height . "\n\n";

#$width = 500;
#$height = 500;

my $pxFile = $ARGV[0] . ".img.txt";

print "Getting pixels...\n";
my $cmd = "cat \"$ARGV[0]\" | convert - -gravity center txt:- > $pxFile";

print "Doing: $cmd\n";

my $whiteGuys = 0;		#number of samepixels

#print "1\n";

my @colCounts = ();
for(my $i = 0; $i < $width; $i++)
{	
	push(@colCounts, 0);
}
#print "2\n";

my $modLine = "(  0,  0,  0,  255)  #FF0000  red";
#print "3\n";

print "$whiteGuys\n";


my $midIndex = floor($#colCounts/2);
my $range = floor($#colCounts/3);
my $lowAvg = 0;
my $midAvg = 0;
my $highAvg = 0;

print "Cols, middle one, range: " . $#colCounts . " ==> $midIndex ==> $range -- " . "\n";

for(my $i = 0; 
    $i < ($range+1); $i++)
{
	$lowAvg += $colCounts[$i];
}
$lowAvg = $lowAvg/$range;

for(my $i = ($range+1); 
    $i < (2*$range + 1); $i++)
{
	$midAvg += $colCounts[$i];
}
$midAvg = $midAvg/$range;

for(my $i = (2*$range+1); 
    $i < $#colCounts; $i++)
{
	$highAvg += $colCounts[$i];
}
$highAvg = $highAvg/$range;

print "BG Pixels/col: \n Low avg: $lowAvg\nMid Avg: $midAvg\nHigh Avg: $highAvg\n\n\n";
if(-e $ARGV[1])
{
	open(OUT, ">>$ARGV[1]");
	print OUT "$ARGV[0], $lowAvg, $midAvg, $highAvg\n";
	close(OUT);
}
else
{
	open(OUT, ">$ARGV[1]");
	print OUT "$ARGV[0], $lowAvg, $midAvg, $highAvg\n";
	close(OUT);
}

sub trim($)
{
	my $string = shift;
	$string =~ s/^\s+//;
	$string =~ s/\s+$//;
	return $string;
}














