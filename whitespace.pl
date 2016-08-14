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

  $image = Image::Magick->new;
  $x = $image->Read($ARGV[0]);

  print "Finding..." . $ARGV[0] . "\n";
  my $bgColor = getBGcolor($ARGV[0]);

  print "BG Color: $bgColor\n\n";

($width, $height, $size, $format) = $image->Ping($ARGV[0]);

print "W x H: " . $width . " x " . $height . "\n\n";

#$width = 500;
#$height = 500;

my $pxFile = $ARGV[0] . ".img.txt";

print "Getting pixels...\n";
#my $cmd = "cat \"$ARGV[0]\" | convert - -gravity center txt:- > $pxFile";
my $cmd = "cat \"$ARGV[0]\" | convert - -gravity center txt:- > $pxFile";

print "Doing: $cmd\n";

#if(!(-e $pxFile))
if(1 == 1)
{
	my $jnk = `$cmd`;
}

#exit();

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

open(FILE, $pxFile) or die ("Cannot find $pxFile\n\n");
#print "3.1: opening " . $pxFile . "_modded.txt\n";
#open(OUT, ">/var/www/mementoImportance/" . $pxFile . "") or die ("Cannot find $pxFile\n\n");
#print "3.2\n";
my $line = <FILE>; 	#get first line off

#print OUT "$line";

my $prevX = 0;
my $runCounter = 0;
while(my $line = <FILE>)
{
	#print "4\n";
	$line = trim($line);
	#print "LINE: $line\n";
	my $origLine = $line;

	$line =~ s/ +/ /g;

	#print "LINE: $line\n";	
	#sleep(1);

	my @arr = split(/:/, $line);
	my $xy = $arr[0];
	my @arr = split(/#/, $line);
	my $tmp = trim($arr[1]);
	my @arr = split(/ /, $tmp);
	my $hex = trim($arr[0]);

	my @arr = split(/,/, $xy);
	my $x = trim($arr[0]);
	my $y = trim($arr[1]);

	my $outLine = "$x,$y: $modLine";

	#if($prevX < $x)
	#{
		#push(@colCounts, 0);
		#$prevX = $x;
		#$runCounter++;
		#$colCounts[$prevX] = 0;
	#}

	if($USEVIEWPORT == 1 && $x <= $XLIM && $y <= $YLIM)
	{
		#print "$x,$y ==> $hex == $bgColor\n";
		#sleep(1);
		#if($x > 900)
		#{			 
		#	print "$x,$y: $hex == $bgColor!\n";
		#}

		$hex =~ s/#//;
		if(length($hex) > 6)
		{
			$hex = "FFFFFF";
		}
		if($hex eq $bgColor)
		{
			#if($x > 500 && $x < 700 && $y == 500)
			#if($x > 900)
			#{			 
			#	print "$x,$y," . $colCounts[$x] . ": $hex == $bgColor!\n";
			#}
			#sleep(1);
			$whiteGuys++;
			$colCounts[$x]++;
			#$colCounts[$prevX]++;
			
			#print OUT $outLine . "\n";
		}
		else
		{
			#print OUT $origLine . "\n";
		}
	}
	elsif($USEVIEWPORT == 0)
	{
		$hex =~ s/#//;
		if($hex eq $bgColor)
		{
			#print "Same!\n";
			$whiteGuys++;
			$colCounts[$x]++;
			#$colCounts[$prevX]++;
		}
	}
	#print "$xy ==> $hex\n\n";
	

	##debugging
	#if($runCounter > 700)
	#{
	#	print $whiteGuys . " ==> \n";
	#
	#	for(my $i = 400; $i < 700; $i++)
	#	{
	#		print $colCounts[$i] . "\n";
	#	}
	#
	#	exit();
	#}
}
#close(OUT);
close(FILE);

print "$whiteGuys\n";

my $cmd = "cat \"" . $pxFile . "_modded.txt\" | convert - -gravity center png:- > \"" . $ARGV[0] . "_modded.png\"";
#print "CMD: $cmd\n";
#my $jnk = `$cmd`;

#print "ranit: $jnk\n\n\n";

#####I'm thinking the following:
###find the middle of the image, and get the # of pixels
###in that middle column. Then, find the average number
### of the middle third of the page.
###if avgs of the left and right thirds are less than
###the middle third, it is centered.
#print $colCounts[$i] . "\n";

#for my $c (@colCounts)
#{
#	print "$c\n";
#}

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
	print OUT "$ARGV[0], [$lowAvg, $midAvg, $highAvg]\n";
	close(OUT);
}
else
{
	open(OUT, ">$ARGV[1]");
	print OUT "$ARGV[0], [$lowAvg, $midAvg, $highAvg]\n";
	close(OUT);
}



sub getBGcolor($)
{
	my $rgb = new Color::Rgb(rgb_txt=>'rgb.txt');
	my $uri = trim($ARGV[0]);
	$uri =~ s/\.png/\.html/i;
	if($uri =~ /^http:\/\//i)
	{
	}
	else
	{
		$uri =~ s/\.*\///;
		$uri = "http://www.cs.odu.edu/~jbrunelle/wsdl/positiontest/testing/theOutFile.png";
		#$uri = "http://justinhome2/mementoImportance/$uri";
	}
	my $cmd = "phantomjs --local-to-remote-url-access=yes ./bgcolor.js \"$uri\"";

	my $bg = "";
 	eval {
                        if($DEBUG == 1)
                        {
                                print "RUnning...$pjs\n";
                        }
                        local $SIG{ALRM} = sub {die "alarm\n"};
                        alarm 90;
                        #print "RUnning...$pjs\n";
			$bg = `$cmd`;
			$bg = trim($bg);
                        alarm 0;
        };


	##this is for the crappy JS code errors
	my @arr = split("\n", $bg);
	if($#arr > 0)
	{
		$bg = trim($arr[$#arr]);
	}
	else
	{
		$bg = "FFFFFF";
	}

	my $temp = $bg;

	if($temp =~ m/rgb/i)
	{
		$temp =~ s/rgb//i;
		$temp =~ s/\(//i;
		$temp =~ s/\)//i;
	
		my @arr3 = split(",", trim($temp));
		$bg = $rgb->rgb2hex(@arr3);
	}

	if(length($bg) > 6)
	{
		$bg = "FFFFFF";
	}
	if($bg eq "00000000")
	{
		$bg = "FFFFFF";
	}

	return $bg;
}

sub getBGcolor_old($)
{
	my $bg = "white";

	my $loc = $ARGV[0];
	$loc =~ s/\.png/\.html/i;

	print "$loc\n";
	

	open(IN, $loc);
	my @data = <IN>;
	close(IN);

	my $html = join("\n", @data);
	if ($html =~ m/background-color:/ig)
	{
		#background-color: #ffffff
		##split on the CSS tag
		my @arr = split(/background-color: /, $html);
		if($arr[1] =~ m/rgb/i)
		{
			print "1\n";
			my @arr2 = split(/;/, $arr[1]);
			my @arr3 = split(",", trim($arr2[0]));
			my $temp = $arr2[0];
			$temp =~ s/rgb//i;
			$temp =~ s/\(//i;
			$temp =~ s/\)//i;
			my @arr3 = split(",", trim($temp));
			$bg = $rgb->rgb2hex(@arr3);
		}
		else
		{
			my @arr2 = split(/ /, $arr[1]);
			$bg = $arr2[0];
		}
		$bg = trim($bg);
	}
	elsif ($html =~ m/background: /ig)
	{
		#background-color: #ffffff
		##split on the CSS tag
		my @arr = split(/background: /, $html);
		if($arr[1] =~ m/rgb/i)
		{
			print "2\n";
			my @arr2 = split(/;/, $arr[1]);
			my $temp = $arr2[0];
			$temp =~ s/rgb//i;
			$temp =~ s/\(//i;
			$temp =~ s/\)//i;
			my @arr3 = split(",", trim($temp));
			$bg = $rgb->rgb2hex(@arr3);
		}
		else
		{
			my @arr2 = split(/ /, $arr[1]);
			$bg = $arr2[0];
		}
		$bg = trim($bg);
	}
	elsif($html =~ m/body bgcolor/ig)
	{
		print "3\n";
		#<body bgcolor="#E6E6FA">
		##split on body tag
		if($arr[1] =~ m/rgb/i)
		{
			print "3.1\n";
			my @arr2 = split(/;/, $arr[1]);
			my $temp = $arr2[0];
			$temp =~ s/rgb//i;
			$temp =~ s/\(//i;
			$temp =~ s/\)//i;
			my @arr3 = split(",", trim($temp));
			$bg = $rgb->rgb2hex(@arr3);
		}
		else
		{
			
			my @arr = split(/bgcolor= /, $html);
			my @arr2 = split(/>/, $arr[1]);
			$bg = trim($arr2[0]);
		}
	}
	return $bg;
}


sub getBGcolor_old2($)
{
	my $rgb = new Color::Rgb(rgb_txt=>'/etc/X11/rgb.txt');
	my $uri = trim($ARGV[0]);
	$uri =~ s/\.png/\.html/i;
	if($uri =~ /^http:\/\//i)
	{
	}
	else
	{
		$uri =~ s/\.*\///;
		$uri = "http://192.168.1.2/mementoImportance/$uri";
	}
	my $cmd = "phantomjs --local-to-remote-url-access=yes bgcolor.js \"$uri\"";
  	#print "Finding..." . $cmd . "\n";

	my $bg = "";
 	eval {
                        if($DEBUG == 1)
                        {
                                print "RUnning...$pjs\n";
                        }
                        local $SIG{ALRM} = sub {die "alarm\n"};
                        alarm 90;
                        #print "RUnning...$pjs\n";
			$bg = `$cmd`;
			$bg = trim($bg);
                        alarm 0;
        };

	##this is for the crappy JS code errors
	my @arr = split("\n", $bg);
	$bg = trim($arr[$#arr]);

	if($bg =~ m/^rgb/i)
	{
		my $temp = $bg;
		$temp =~ s/rgb//i;
		$temp =~ s/\(//i;
		$temp =~ s/\)//i;
		my @arr3 = split(",", trim($temp));
		return @arr3;
	}
	else
	{
		my @arr3 = $rgb->hex2rgb($bg);
	}
	

	return $bg;
}



sub trim($)
{
	my $string = shift;
	$string =~ s/^\s+//;
	$string =~ s/\s+$//;
	return $string;
}














