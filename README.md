[comment]: https://docs.google.com/presentation/d/1sh8-9zQhLXGqSJWvE5QCK3ysCcCaGAim8pCoa4T-62I/edit?usp=sharing

# Memento Damage

Memento Damage is a tool that helps to estimate the damage that happens on a memento. Although the main idea is to calculate damage on memento (URI-M), this tool can also be used for calculating damage on a live web page (URI-R).  </br>
There are 2 ways to use this tool:
- [Online service](#online-service)
  - [Website](#website)
  - [REST API](#rest-api)
- [Local service](#local-service)
  - [Docker](#docker)
  - [Library](#library)

## Online Service
### Website
The website version can be used by accesing http://memento-damage.cs.odu.edu/. This service is suitable for the purpose of finding the damage of single URI. To use the tool, user just simply type or paste the URI to the damage-check textbox form, and type enter or click check button.

![](https://github.com/oduwsdl/web-memento-damage/raw/screenshot/pasted%20image%200.png)

The output will be displayed on the result page, on tab ‘summary’. Other tabs in the result page provide the details of the damage according to the resources types: images, stylesheets, javascript, multimedia, and text. Tab ‘screenshot’ provide the screenshot of the URI and tab ‘log’ gives the details of the process that happens during the damage calculation.

![](https://github.com/oduwsdl/web-memento-damage/raw/screenshot/online-2.png)

### REST API
REST API facilitates damage calculation from any HTTP Client (e.g. web browser, curl, etc) and give output in JSON format. This enables user to do further analysis with the output. User can create a script and utilize the REST API to calculate damage on few number of URIs (e.g. 5). Here are some simple examples of accessing memento-damage service using REST API:


#### CURL
```
curl http://memento-damage.cs.odu.edu/api/damage/http://odu.edu/compsci
```

#### Python
```
import requests
resp = requests.get('http://memento-damage.cs.odu.edu/api/damage/http://odu.edu/compsci')
print resp.json()
```

## Local Service
This option is suitable for calculating the damage on a myriad number of URIs (e.g. 10.000 URIs).  The web service http://memento-damage.cs.odu.edu/ clearly cannot handle this. Therefore, we provide an option so that users can install and run the Memento Damage tool on their own machine.

### Install

To install Memento Damage locally, simply navigate to the project's root directory and run the following commands.

```
pip install .

npm install .
```

### Run

### Command-line

#### Load generic URIs

```
memento-damage -c <DATA_PATH> <URI>
```

#### Load URIs in batch

To load multiple URIs for analysis provide a file path in place of a Web URI, prefixed with the keyword `file:`. Input files should be in CSV format, where each line is formatted as `<URI>,` (note the trailing comma) or `<URI>, <WARC_FILE_NAME>`.

```
memento-damage -c <DATA_PATH> file:<CSV_INPUT_FILE>
```


#### Load WARC files

Load WARCs using -w flag; local warc files should have relatively little load time unless they are very large in size, remote warcs (-w http://xyz.warc) might require normal or longer timeout set. If your WARC file is very large, consider using the [WACZ format](https://specs.webrecorder.net/wacz/1.1.1/). To load a WARC file, a `-W` flag is required, specifying from where to load the file. In order to load multiple WARCS from an input CSV file all WARC files must exist in the same directory.

```
memento-damage -c <DATA_PATH> -W <LOCAL_WARC_DIR> -w <WARC_FILENAME> <URI>
```

### Web Service
To run a local version of the Web service, simply provide a directory where data will be stored using the `-c` (for 'cache') flag.

```
memento-damage-web -c <DATA_PATH>
```

The Memento Damage Web service will run on port `8080` by default. Optionally, a custom port and host IP can be specified using the `-H` and `-P` flags

```
memento-damage-web -c <DATA_PATH> -H 1.2.3.4 -P 9999
```

### Advanced configurations

For further customizations, such as enabling debugging output and timeouts, please use the `-h` or `--help` flags to display all command options.