#!/usr/bin/perl
#

my $DEBUG = 4;

##list of URIs for file 1 here
my $archiveitFile = "/storage/URIM_Snapshots/ArchivabilityOverTime/archiveit_uris_scrubbed_1000.o";

##list of URIs for file 2 here
my $twitterFile = "/storage/URIM_Snapshots/ArchivabilityOverTime/actualURIs.o";

##timegate location
my $iaTimegate = "http://web.archive.org/web/timemap/link/";
#my $iaTimegate = "http://mementoproxy.cs.odu.edu/aggr/timemap/link/";

##output location for file 1 here
my $aitSTATS = "./aitDamage_newWeights.o";

##output location for file 2 here
my $twitSTATS = "./twitDamage.o";

my $AITONLY = 1;

open(FILE, ">>$aitSTATS");
print FILE "theURIM, PNG, datetime, Embedded Resource, Damage\n";
close(FILE);

open(FILE, $archiveitFile);
my @ait = <FILE>;
close(FILE);

open(FILE, $twitterFile);
my @twit = <FILE>;
close(FILE);

##run 1 went to 140
my $id1 =0;
for(my $i = 0; $i< $#ait+1; $i++)
#for my $u (@ait)
{
	$u = trim($ait[$i]);

	if($DEBUG == 1)
	{
		#$u = "http://www.fubiz.net/2009/06/10/bad-food-bad-dog/";
	}

	$u = trim($u);

	if($DEBUG >= 1)
	{
		print "U: $u\n";
		sleep(5);
	}

	my $curlit = "curl \"$iaTimegate" . "$u\"";

	my @timemap;
	if($DEBUG == 3)
	{
		open(FILE, "./download");
		@timemap = <FILE>;
		close(FILE);
	}
	else
	{
		eval {
			if($DEBUG == 1 || 1 < 2)
			{
				print "Curling $curlit\n";
			}
                        local $SIG{ALRM} = sub {die "alarm\n"};
                        alarm 90;
                        @timemap = `$curlit`;
                        alarm 0;
                };
		wait();
	}

	my $id = 0;
	my $dt = "";
	my $thepng = "DNE";
	my $lastYear = 0;

	for my $t (@timemap)
	{
	   if($t =~ m/TOTAL DAMAGE/g)
	   {
		open(FILE, ">>$aitSTATS");
		print FILE trim($t) . "\n";
		close(FILE);
	   }
	   else
	   {
		my $mem = "";
		$t = trim($t);
		$mem = trim(findURIM($t));

		#print "MEM: $mem\n\n";

		if($DEBUG == 1)
		{
			#$mem = "http://web.archive.org/web/20090614041133/http://www.fubiz.net/2009/06/10/bad-food-bad-dog/";
		}
		
		$dt = findDT($mem);

		#print "DT: $dt\n\n";

		my $year = substr($dt, 0, 4);

		if($DEBUG == 1)
		{
			print "DateTime of $year -- $mem is $dt\n\n";
		}

			#print "DateTime of $year -- $mem is $dt\n\n";

		if(!($mem eq "") && ($year > $lastYear))
		{
			#print "$year > $lastYear\n\n";

			$lastYear = $year;
			my $pjs = "/var/www/phantomjs/bin/phantomjs rasterize.js \"$mem\" ./junk.png  "
				. "./junk.html  ./junk.404";

			my $grepCounter = 0;
			my @grepper;
			while($#grepper < 0 && $grepCounter < 1000)
			{
				my $thegrep = "grep \"$mem\" /storage/URIM_Snapshots/ArchivabilityOverTime/ait/"
						. $grepCounter . "_*.404";
				##comes out as ./twit/100_4_20090614041133.404:1, http://web.archive.org/web/20090614041133/http://www.fubiz.net/2009/06/10/bad-food-bad-dog/, 200, 200

				if($DEBUG == 1)
				{
					print "Grepping: $thegrep\n\n";
				}
				@grepper = `$thegrep`;

				#print "The grepper: " . $#grepper . " ==> " . $grepper[0] . "\n\n";

				$grepCounter++;
			}
			

			#if($#grepper > -1)
			if($#grepper > -1)
			{
				$thepng = $grepper[0];
				@thejnk = split(/,/, $thepng);
				$thepng = trim($thejnk[0]);
				$thepng =~ s/:1//i;
				$thepng =~ s/\.404/\.png/i;
				$thepng = trim($thepng);

				if($DEBUG >= 1)
				{
					print "the PNG: $thepng\n";
					#sleep(10);
				}
			}
			else
			{
				$thepng = "./testing/" . $dt . "_$i.png";
				my $cpcmd = "cp ./testing/theOutFile.png $thepng";
				#my $tmp = `$cpcmd`;
			}

			my $measureCmd = "perl rerun_measureMemento.pl \"$mem\"";

			if($DEBUG >= 1)
			{
				print "Running $measureCmd\n\n";
			}


			my @tmp;
			#######use this for the PJSs if they don't finish...
			#unless((-e $target404))
                        #{
                                eval {
                                        local $SIG{ALRM} = sub {die "alarm\n"};
                                        alarm 400;
                       			print "start run...\n";
                                        @tmp = `$measureCmd`;
                       			print "end run!\n";

                                        alarm 0;
                                };
				wait();
                        #}
			my $killcmd = "killall phantomjs";
			my $jnk = `$killcmd`;

			print "Missing $#tmp resources...\n";

			open(FILE, ">>$aitSTATS");
			if($#tmp > -1)
			{
				foreach my $c (@tmp)
				{
					$c = trim($c);

					if($DEBUG >= 1)
					{
						print "Got C: $c\n";
						print "TO FILE::: $mem, $dt, $thepng, " . trim($c) . "\n";
					}

					unless($c eq "")
					{
						print FILE "$mem, $dt, $thepng, " . trim($c) . "\n";
					}
				}
			}
			else
			{
				print FILE "$mem, $dt, $thepng, NO DAMAGE, 0\n";
			}
			close(FILE);
		}

		$id++;

	   }##end unless
	}

	if($DEBUG == 1)
	{
		#exit();
	}
	$id1++;
}


if($AITONLY == 1)
{
	exit();
}

if($DEBUG >= 1)
{
	print "\n\n\n  STARTING TWITTER!!!!!!!\n\n\n";
	sleep(60);
}


sub isHTML($)
{
	my $line = $_[0];
	my $htmlFile = $_[1];
	my $dt = $_[2];

	#print "Params: $htmlFile :: $dt \n\n";

	my @splat = split(/, /, $line);
	my $r = trim($splat[1]);
	my $code = trim($splat[2]);

	$r =~ s/http:\/\/web\.archive\.org\/web\/.*\/http//i;
	

	if($DEBUG == 1)
	{
		print "grepping: grep \"$r\" $htmlFile | wc -l\n";
	}

	my $l = `grep "$r" $htmlFile | wc -l`;

	$l = trim($l);
	if($l > 0)
	{
		return 1;
	}
	return 0;
}

sub findDT($)
{
	my $m = $_[0];
	$m =~ s/http:\/\/web\.archive\.org\/web\///i;
	my @splat = split(/\//, $m);
	$m = trim($splat[0]);

	return $m;
}

sub findURIM($)
{
	$t = $_[0];
	if($DEBUG == 1)
	{
		print "Param: $t\n";
	}

	my $mem = "";
	if($t =~ m/first memento/i)
	{
		$mem = $t;
	}
	elsif($t =~ m/last memento/i)
	{
		$mem = $t;
	}
	elsif($t =~ m/first last memento/i)
	{
		$mem = $t;
	}
	elsif($t =~ m/rel="memento/i)
	{
		$mem = $t;
	}
	

	if(!($mem eq ""))
	{
		if($DEBUG == 1)
		{
			print "Got memento: $mem\n";
		}
		
		$mem =~ s/<//;
		$mem =~ s/>//;
		$mem =~ s/; rel=".*"; datetime=".*"//;
		$mem =~ s/,$//;
		
		if($DEBUG == 1)
		{
			print "And it has a URI-M: $mem\n\n";
		}
	}


	return $mem;
}









sub trim($)
{
        my $string = shift;
        $string =~ s/^\s+//;
        $string =~ s/\s+$//;
        return $string;
}
