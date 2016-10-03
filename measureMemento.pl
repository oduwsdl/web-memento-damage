#!/usr/bin/perl
#

use URI;
use HTML::Strip;
use HTML::TokeParser::Simple;

###example from *.404 files:
#http://www.cs.odu.edu/files/spacer.gif, img, [1,1], [127,7], [1024,777], 200


my $USE_LEFTOVERS = 0;

##global weight parameters
my $MMweight = 0.50;
my $CSSweight = 0.05;
my $proportion = 3.0/4.0;
my $IMGweight = $proportion * (1-($MMweight + $CSSweight));
my $TXTweight = 1 -($MMweight + $CSSweight + $IMGweight);
my $wordsPerImg = 1000;

##where our phantomjs command lives
my $pjs = "phantomjs";


if($#ARGV < 0)
{
        print "USAGE: perl measureMemento.pl [URI-M]\n";
        exit();
}


##the thing to measure
my $urim = $ARGV[0];


##1) Do PjS
##2) Find BG Coverage of images (Sum image sizes)
##3) Find Potential Damage (send parameters for global weights)
#####3.1) # CSS tags references
#####3.2) MM (add all occurences and apply global weight)
#####		Size & centrality should sum to 1
#####3.3) Imgs (add all and apply global weight)
#####		Size & centrality should sum to 1
#####3.4) TXT (weight applied)
#####		boolean
##4) Find Actual Damage (same as 3) but only do codes > 399
##5) Print report
##### each uri-m with damage [0,1]
##### total page damage [0,1]


##define save location
my $toSave = "./testing/theOutFile";

#print "Processing $urim...\n";

if($urim)
{
	my $pjsCmd = "phantomjs ./rasterize.js "
			. "\"$urim\" "
			. "$toSave.png "
			. "$toSave.html "
			. "$toSave.404";
	my $pjsTimeout = 180; 		##seconds

	##1)
	print "=======================================================================\n";
	print "Running $pjsCmd...\n";
	my @returnedStuff = RunCmd($pjsCmd, $pjsTimeout);
	#print "Done!\n\n\n";

	##2) find percent coverage of the viewport by images
	my $pixelCoverage = pctCoverage("$toSave.404");
	#print "Covering $pixelCoverage\n";

	##3)
	my @theMissing = findMissing("$toSave.404");
	#for(my $i = 0; $i <= $#theMissing; $i++)
	#{
	#	print "Missing " . trim($theMissing[$i]) . "\n";
	#}

	#print "Initial Weights: $CSSweight, $IMGweight, $TXTweight, $MMweight\n";

	my $potentialDamage = findPotentialDamage($toSave, $MMweight, 
			$CSSweight, $IMGweight, $TXTweight, $wordsPerImg);

	#print "Potential DONE\n\n";
	#print "After Weights: $CSSweight, $IMGweight, $TXTweight, $MMweight\n";

	#print "\n\nProcessing actual damage...\n\n";
	my %actualDamages = findActualDamage("$toSave", $MMweight, 
			$CSSweight, $IMGweight, $TXTweight, $wordsPerImg, 
			$potentialDamage);

	#print "\n\nGenerating report...\n\n";
	printReport(\%actualDamages);	
	
}##end unless urim


############################################################
############################################################


sub pctCoverage($)
{
	#http://www.cs.odu.edu/files/spacer.gif, img, [1,1], [127,7], [1024,777], 200

	open(FILE, $_[0]);
	my @uris = <FILE>;
	close(FILE);

	#print "\nReading $_[0] of length $#uris\n";

	my $viewport = 0;
	my $imgCoverage = 0;	

	for(my $i = 0; $i <= $#uris; $i++)
	{
		#print "Running...$uris[$i]\n";
		$uris[$i] = trim($uris[$i]);
		my @splat = split(", ", $uris[$i]);
		
		unless($viewport > 0)
		{
			my @tmp = split(",", trim($splat[4]));
			my $x = $tmp[0];
			my $y = $tmp[1];
			$x =~ s/\]//i;
			$x =~ s/\[//i;
			$y =~ s/\]//i;
			$y =~ s/\[//i;

			$x = trim($x);
			$y = trim($y);

			$viewport = $x * $y;

			#print "viewport: $viewport = $x * $y\n";
		}

		if($viewport <= 0 || $viewport eq "")
		{
			$viewport = 1024*777;
		}

		if($splat[1] eq "img" || $splat[1] eq "multimedia")
		{

			my @tmp = split(",", trim($splat[2]));
			my $x = $tmp[0];
			my $y = $tmp[1];
			$x =~ s/\]//i;
			$x =~ s/\[//i;
			$y =~ s/\]//i;
			$y =~ s/\[//i;

			$x = trim($x);
			$y = trim($y);

			$imgCoverage += $x*$y;
		
			#print "Image Coverage $imgCoverage += $x*$y\n";

			if($responseCode > 399)
			{
				push(@missingStuff, $contents[$i]);
			}
		}
		else
		{
			#print "Ignoring $uris[$i]\n";
		}
	}
	#print "$imgCoverage is covered $imgCoverage/$viewport...\n";
	my $pctCov = $imgCoverage/$viewport;
	return $pctCov;
}


sub findMissing($)
{
	open(FILE, $_[0]);
	my @uris = <FILE>;
	close(FILE);

	#print "Processing $_[0] of $#uris\n";

	my @missingStuff = ();

	for(my $i = 0; $i <= $#uris; $i++)
	{
		$uris[$i] = trim($uris[$i]);
		my @splat = split(", ", $uris[$i]);
		my $responseCode = trim($splat[$#splat]);

		#print "Response: $responseCode\n";

		if($responseCode > 399)
		{
			unless($uris[$i] eq "http://web.archive.org/static/css/styles.css")
			{
				#print "Found Missing $uris[$i]\n";
				push(@missingStuff, $uris[$i]);
			}
		}
	}
	return @missingStuff;
}


#usage: "$toSave", $MMweight, $CSSweight, $IMGweight, $TXTweight
sub findPotentialDamage($)
{
	#print "Finding potential damage...\n";

	my $isPotential = 1;

	# need to find all things in the 404 file, iterate over them and call findImportance for each
	open(FILE, "$_[0].404");
	my @uris = <FILE>;
	close(FILE);

	$MMweight  = $_[1];
	$CSSweight = $_[2];
	$IMGweight = $_[3];
	$TXTweight = $_[4];
	$wordsPerImg = $_[5];

	my %damages;

	#print "Processing potential damage: $_[0].404\n";

	for(my $i = 0; $i <= $#uris; $i++)
	{
		$uris[$i] = trim($uris[$i]);
		my @splat = split(", ", $uris[$i]);
		my $u = trim($splat[0]);
		
		unless($uris[$i] eq "http://web.archive.org/static/css/styles.css")
		{
			$damages{$u} = findImportance($uris[$i], "$_[0].png", 
				$_[1], $_[2], $_[3], $_[4], $isPotential);
		}
		## find importance now returns this: <value, type> such as "0.98, img"
		#print "Potential Damage $damages{$u} for $u\n";
	}
	$damages{"txt"} = findTxtImportance("$_[0].html", $wordsPerImg);

	#print "Potential Damage of TEXT is " . $damages{"txt"} . "\n";

	my $total = 0;
        my $numRes = 0;


	my $totalImg = 0;
        my $numResImg = 0;
	my $totalCss = 0;
        my $numResCss = 0;
	my $totalMM = 0;
        my $numResMM = 0;
	my $totalTxt = 0;
        my $numResTxt = 0;


	while(my ($key, $value) = each(%damages))
	{
		#print "Potential Damage $key ==> $value\n";
		##value is "0.98, img"
		my @splat = split(/, /, $value);

		$splat[0] =~ s/\[//i;
		$splat[0] =~ s/\[//i;
		$splat[1] =~ s/\]//i;
		$splat[1] =~ s/\]//i;

		$splat[0] = trim($splat[0]);
		$splat[1] = trim($splat[1]);

		#print "Damage,Type:$splat[0],$splat[1]...\n";

		if($splat[1] eq "img")
		{
			$totalImg += $splat[0];
			$numResImg++;
		}
		elsif($splat[1] eq "css")
		{
			$totalCss += $splat[0];
			$numResCss++;
		}
		elsif($splat[1] eq "multimedia")
		{
			$totalMM += $splat[0];
			$numResMM++;
		}
		elsif($splat[1] eq "txt")
		{
			$totalTxt += $splat[0];
			$numResTxt++;
		}
	}

	my $finalImg = 0;
	my $finalCss = 0;
	my $finalMM = 0;
	##this should be 1 always

	my $leftovers = 0;
	if($numResCss <= 0)
	{
		$leftovers += $CSSweight;
	}
	else{
	}
	if($numResImg <= 0)
	{
		$leftovers += $IMGweight;
	}
	else{
	}
	if($numResMM <= 0)
	{
		$leftovers += $MMweight;
	}
	else{
	}

	if($USE_LEFTOVERS == 1)
	{

	##redistribute the leftovers
	if($numResCss > 0)
	{
		$finalCss = $totalCss/$numResCss;
	}
	else
	{
		$IMGweight += $numResImg/($numResImg + $numResMM + $numResTxt) * $CSSweight;
		$MMweight += $numResMM/($numResImg + $numResMM + $numResTxt) * $CSSweight;
		$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $CSSweight;
	}
	if($numResImg > 0)
	{
		$finalImg = $totalImg/$numResImg;
	}
	else
	{
		$CSSweight += $numResCss/($numResCss + $numResMM + $numResTxt) * $IMGweight;
		$MMweight += $numResMM/($numResCss + $numResMM + $numResTxt) * $IMGweight;
		$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $IMGweight;
	}
	if($numResMM > 0)
	{
		$finalMM = $totalMM/$numResMM;
	}
	else
	{
		$CSSweight += $numResCss/($numResCss + $numResImg + $numResTxt) * $MMweight;
		$IMGweight += $numResImg/($numResCss + $numResImg + $numResTxt) * $MMweight;
		$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $MMweight;
	}
	
	}##end if use leftovers...

	my $finalTXT = $totalTxt/$numResTxt * $TXTweight;
	$finalCss = $totalCss * $CSSweight;
	$finalMM = $totalMM * $MMweight;
	$finalImg = $totalImg * $IMGweight;

	#print "\ncalculated total damage:\n";
	#print "CSS: $finalCss = $totalCss * $CSSweight;\n";
	#print "MM: $finalMM = $totalMM * $MMweight;\n";
	#print "IMG: $finalImg = $totalImg * $IMGweight;\n\n";

	#print "Avg total image $finalImg = $totalImg/$numResImg * $IMGweight;\n";

	$total = $finalImg + $finalCss + $finalMM + $finalTXT;

	#print "POTENTIAL TOTAL:  $total = $finalImg + $finalCss + $finalMM + $finalTXT\n\n";
	#print "Calculated Weights: $CSSweight, $IMGweight, $TXTweight, $MMweight\n";

	###do the accumulators and parsing stuff to get a normalized value.

	return $total;
}

#usage: "$toSave.404", $MMweight, $CSSweight, $IMGweight, $TXTweight
sub findActualDamage($)
{
	# need to find 404s, iterate over them and call findImportance for each
	my @uris = findMissing("$toSave.404");

	open(FILE, "$toSave.404");
	my @alluris = <FILE>;
	close(FILE);
	
	#print "Finding actual damage...\n";

	$MMweight  = $_[1];
	$CSSweight = $_[2];
	$IMGweight = $_[3];
	$TXTweight = $_[4];
	$wordsPerImg = $_[5];
	$potentialDamage = $_[6];

	my $isPotential = 0;

	my %damages;

	for(my $i = 0; $i <= $#uris; $i++)
	{
		#print "Missing $uris[$i]\n";
		$uris[$i] = trim($uris[$i]);
		my @splat = split(", ", $uris[$i]);
		my $u = trim($splat[0]);
		
		$damages{$u} = findImportance($uris[$i], "$_[0].png", 
			$_[1], $_[2], $_[3], $_[4], $isPotential);
		## find importance now returns this: <value, type> such as "0.98, img"
	}

	#print "$#uris/$#alluris = " . ($#uris/$#alluris) . "\n";

	$damages{"PCT_MISSING"} = ($#uris + 1)/($#alluris + 1);


	###copy and paste from findPotentialDamage
	#$damages{"txt"} = findTxtImportance("$_[0].html", $wordsPerImg);


	my $total = 0;
        my $numRes = 0;


	my $totalImg = 0;
        my $numResImg = 0;
	my $totalCss = 0;
        my $numResCss = 0;
	my $totalMM = 0;
        my $numResMM = 0;
	my $totalTxt = 0;
        my $numResTxt = 0;


	while(my ($key, $value) = each(%damages))
	{
	        #print "ACTUAL Damage $key ==> $value\n";
		##value is "0.98, img"
		my @splat = split(/, /, $value);

		$splat[0] =~ s/\[//i;
		$splat[0] =~ s/\[//i;
		$splat[1] =~ s/\]//i;
		$splat[1] =~ s/\]//i;

		$splat[0] = trim($splat[0]);
		$splat[1] = trim($splat[1]);

		#print "Type:$splat[1]...\n";

		if($splat[1] eq "img")
		{
			$totalImg += $splat[0];
			$numResImg++;
		}
		elsif($splat[1] eq "css")
		{
			$totalCss += $splat[0];
			$numResCss++;
		}
		elsif($splat[1] eq "multimedia")
		{
			$totalMM += $splat[0];
			$numResMM++;
		}
		elsif($splat[1] eq "txt")
		{
			$totalTxt += $splat[0];
			$numResTxt++;
		}
	}

	##iff nothing's missing
	if(($numResImg + $numResCss + $numResMM + $numResTxt) <= 0)
	{
		#print "$numResImg + $numResCss + $numResMM + $numResTxt == 0\n\n";
		$damages{"TOTAL"} = 0;
		return %damages;
	}

	#print " = $totalImg/$numResImg * $IMGweight;\n";

	my $finalImg = 0;
	my $finalCss = 0;
	my $finalMM = 0;
	##this should be 1 always
	#my $finalTXT = $totalTxt/$numResTxt * $TXTweight;

	my $leftovers = 0;
	if($numResCss <= 0)
	{
		$leftovers += $CSSweight;
	}
	else{
	}
	if($numResImg <= 0)
	{
		$leftovers += $IMGweight;
	}
	else{
	}
	if($numResMM <= 0)
	{
		$leftovers += $MMweight;
	}
	else{
	}

	##redistribute the leftovers
	####We don't want to redistribute the leftovers; we want to keep the 
	###### redistribution from findPotentialDamage.
	if($numResCss > 0)
	{
		$finalCss = $totalCss/$numResCss;
	}
	#else
	#{
	#	$IMGweight += $numResImg/($numResImg + $numResMM + $numResTxt) * $leftovers;
	#	$MMweight += $numResMM/($numResImg + $numResMM + $numResTxt) * $leftovers;
	#	$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $leftovers;
	#}
	if($numResImg > 0)
	{
		$finalImg = $totalImg/$numResImg;
	}
	#else
	#{
	#	$CSSweight += $numResCss/($numResCss + $numResMM + $numResTxt) * $leftovers;
	#	$MMweight += $numResMM/($numResCss + $numResMM + $numResTxt) * $leftovers;
	#	$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $leftovers;
	#}
	if($numResMM > 0)
	{
		$finalMM = $totalMM/$numResMM;
	}
	#else
	#{
	#	$CSSweight += $numResCss/($numResCss + $numResImg + $numResTxt) * $leftovers;
	#	$IMGweight += $numResImg/($numResCss + $numResImg + $numResTxt) * $leftovers;
	#	$TXTweight += $numResTxt/($numResCss + $numResImg + $numResTxt) * $leftovers;
	#}

	$finalCss = $totalCss * $CSSweight;
	$finalMM = $totalMM * $MMweight;
	$finalImg = $totalImg * $IMGweight;

	$total = $finalImg + $finalCss + $finalMM;

	$damages{"TOTAL"} = $total/$potentialDamage;
	#print "ACTUAL TOTAL:  $total = $finalImg + $finalCss + $finalMM\n\n";
	#print "MEMENTO TOTAL: " . $damages{"TOTAL"} . " = $total/$potentialDamage;\n\n\n";

	###do the accumulators and parsing stuff to get a normalized value.

	return %damages;
}

#usage: $potentialDamage, @actualDamage
sub printReport
{
	my $damages = shift;
	foreach (keys %{$damages})
	{
		print $_, ", ", $damages->{$_}, "\n";
	}
}

sub findTxtImportance($)
{
	open(FILE, "$_[0]");
	my @lines = <FILE>;
	close(FILE);
	
	my $theTxt = "";

	my $content = join(/\n/, @lines);
	#my $hs = HTML::Strip->new();
	#$theTxt = $hs->parse($content);
	#$hs->eof;

	#print "Content: $content\n\n\n";

	my $p = HTML::TokeParser::Simple->new( $_[0] );

	while ( my $token = $p->get_token ) {
		# This prints all text in an HTML doc (i.e., it strips the HTML)
		next unless $token->is_text;
		$theTxt = $theTxt . " " . $token->as_is;
 	}

	#print "Got the text: $theTxt\n\n";

	my @words = split(/\s/, $theTxt);
	my $numWords = $#words;

	#print "Da Werds: $numWords / $_[1]\n\n";

	my $val = ($numWords)/$_[1];

	return "[$val, txt]";
}

##find damage value of a thing. Usage: uri-m, $toSave.png
sub findImportance($)
{
	my $line = $_[0];
	my $thePng = $_[1];
	$MMweight = $_[2];
	$CSSweight = $_[3];
	$IMGweight = $_[4];
	$TXTweight = $_[5];
	$isPotential = $_[6];


	my @splat = split(", ", $line);

	my $fileName = trim($splat[0]);
	my $type = trim($splat[1]);
	
	if($type =~ m/img/)
	{
		$importance = findImageImportance($line) . ", img";
	}
	elsif($fileName =~ m/\.css/i)
	{
		$importance = findCssImportance($line, $thePng, $isPotential) . ", css";
	}
	elsif($fileName =~ m/\.js/i)
	{
		##we don't handle this, yet.
		$importance = 1 . ", js";
	}
	elsif($type =~ m/multimedia/i)
	{
		##temporarily using the image importance calculation for this.
			## it should be about the same... position and size and all
		$importance = findImageImportance($line) . ", mm";
	}

	return "[$importance]";
}

sub findImageImportance($)
{
	my $sizeWeight = 0.50;
	my $centralWeight = 0.50;

	#####3.3) Imgs (add all and apply global weight)
	#####		Size & centrality should sum to 1

	my $line = $_[0];

	#print "Finding importance of $line\n";

	my @splat = split(", ", $line);
        
	$location = $splat[3];
	$size = $splat[2];
	$viewport = $splat[4];

	$importance = "";

	#$centralityWeight = 10;
	#$sizeWeight = 0.01;

	$location =~ s/\[//ig;
	$size =~ s/\[//ig;
	$viewport =~ s/\[//ig;
	$location =~ s/\]//ig;
	$size =~ s/\]//ig;
	$viewport =~ s/\]//ig;

	@l = split(",", $location);
        
	@s = split(",", $size);
	@v = split(",", $viewport);
	
	$locX = $l[0];
	$locY = $l[1];
	$sizX = $s[0];
	$sizY = $s[1];
	$vewX = $v[0];
	$vewY = $v[1];

	$midX = $vewX/2;

	##we will add 1/2 of the centraility weight 
	## for each of overlapping the vertical and
	## horizontal middles
	$locationImportance = 0;
        if(($locX + $sizX) > $midX && $locX < $midX)
        {
                #this guy overlaps the middle of the page
                        #on the X axis
                $locationImportance += $centralWeight/2;
		#print "overlaps middle at x; $centralWeight/2 added to get $locationImportance\n";

                if($DEBUG == 1)
                {
                        #print "overlaps middle at x\n\n";
                }
        }
	if(($locY + $sizY) > $midY && $locY < $midY)
        {
                #this guy overlaps the middle of the page
                        #on the Y axis
                $locationImportance += $centralWeight/2;
		#print "overlaps middle at y; $centralWeight/2 added to get $locationImportance\n";

                if($EQNS == 1)
                {
                        #print "overlaps middle at y\n\n";
		}
        }

	##maybe make this the proportion of the pixels in the viewport?
	my $prop = ($sizX * $sizY)/($vewX * $vewY);
	$sizeImportance = ($prop) * $sizeWeight;

	#print "Pixel Proportion: $prop = ($sizX * $sizY)/($vewX * $vewY)\n";
	#print "for size importance $sizeImportance = ($prop) * $sizeWeight\n";

	##return the importance of the image [0,1]
        $importance = ($sizeImportance + $locationImportance);
	#print "Total importance (size + location) => $importance = ($sizeImportance + $locationImportance);\n\n";

	return $importance;
}

sub findCssImportance($)
{
	my $tagWeight = 0.50;
	my $ratioWeight = 0.50;



	#IFF the HTTP code is 200, return 1. else, carry on.
	my $line = $_[0];
	my $thePng = $_[1];
	my $isPotential = $_[2];


	my @splatted = split(", ", $line);

	$fileName = $splatted[0];
	$missingTags = $splatted[1];
	my $code = trim($splatted[$#splatted]);
	if($code == 200)
	{
		return 1;
	}
	elsif($code =~ m/3../)
	{
		return 0;
	}

	$importance = 0;

	if($missedTags > 0)
	{
		$importance += $tagWeight;
	}


	if($isPotential == 0)
	{
		$cmd = "perl ./whitespace.pl $thePng";
		print "Running...$cmd\n";
		my @returnVals = RunCmd($cmd, 300);
		#print "DONE!\n";


		$backgroundColor = trim($returnVals[1]);
		$dimensions = trim($returnVals[3]);
		$colsMidRange = trim($returnVals[8]);
		$low = trim($returnVals[10]);
		$mid = trim($returnVals[11]);
		$high = trim($returnVals[12]);

		@splatted = split(":", $low);
		$low = trim($splatted[1]);
		@splatted = split(":", $mid);
		$mid = trim($splatted[1]);
		@splatted = split(":", $high);
		$high = trim($splatted[1]);

		open(OUT, ">>/home/jbrunelle/public_html/wsdl/damage_revist/dataFiles/iaCSSdistro.txt");
		print OUT "$urim, [$low,$mid,$high]\n";
		close(OUT);

		###stopped at this from the bkp file:
		if(($low + $mid + $high) == 0)
		{
			##will return 0 because there was no data
			$importance += 0;
		}
		elsif(($high)/($low + $mid + $high) > 0.33)
		{
			##if more than 1/3 of the non-BG color is on the right...
			$importance += $high/($low + $mid + $high) * $ratioWeight;
		}
		else
		{
			$importance += $ratioWeight;
		}
	}
	else
	{
		$importance += $ratioWeight;
	}

	return $importance;
}


##run a timed command: usage: RunCmd($cmd, $timeout)
sub RunCmd($)
{
	my @returnvals = [];
	eval{
		local $SIG{ALRM} = sub {die "alarm\n"};
		alarm $_[1];
		@returnVals = `$_[0]`;
		alarm 0;
	};

	wait();

	return @returnVals;
}

sub sameDomain($)
{
	my $goodURI = $_[0];
	my $testURI = $_[1];

	my $url = URI->new($goodURI);
	my $domain1 = $url->host;

	my $url = URI->new($testURI);
	my $domain2 = $url->host;

	if($domain1 =~ m/$domain2/i || $domain2 =~ m/$domain1/i)
	{
		return 1;
	}
	return 0;
}

sub trim($)
{
        my $string = shift;
        $string =~ s/^\s+//;
        $string =~ s/\s+$//;
        return $string;
}

#/**/


