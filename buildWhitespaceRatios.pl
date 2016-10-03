my $cmd = "ls captures/*.png > theImgs.o";
$jnk = `$cmd`;


open(FILE, "./theImgs.o") or die("Unable to open file");
my @imgs = <FILE>;
close(FILE);

my $t1 = "touch ./liveBackground.csv";
my $t2 = "touch ./localBackground.csv";
my $t3 = "touch ./nocssBackground.csv";
my $jnk = `$t1`;
$jnk = `$t2`;
$jnk = `$t3`;

my $count = 7;
#for my $i (@imgs)
while ($count < $#imgs)
{
	my $i = $imgs[$count];

	print "\n\nMeasuring $i\n";
        $i = trim($i);

        $i =~ s/captures\///;

	my $cmd1 = "perl whitespace.pl \"./captures/$i\" ./liveBackground.csv";
	my $cmd2 = "perl whitespace.pl \"./localcaptures/$i\" ./localBackground.csv";
	my $cmd3 = "perl whitespace.pl \"./nocsscaptures/$i\" ./nocssBackground.csv";

	#eval 
	#{
	#	local $SIG{ALRM} = sub {die "alarm\n"};
	#	alarm 120;
	#	print "Running: $cmd1\n";
	#	$jnk = `$cmd1`;
	#};
	#eval 
	#{
	#	local $SIG{ALRM} = sub {die "alarm\n"};
	#	alarm 120;
	#	print "Running: $cmd2\n";
	#	$jnk = `$cmd2`;
	#};
	eval {
		local $SIG{ALRM} = sub {die "alarm\n"};
		alarm 120;
		print "Running: $cmd3\n";
		$jnk = `$cmd3`;
	};

	$count++;
}



sub trim($)
{
        my $string = shift;
        $string =~ s/^\s+//;
        $string =~ s/\s+$//;
        return $string;
}


