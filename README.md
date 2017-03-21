# Memento Damage

Memento Damage is a tool that helps to estimate the damage that happens on a memento. Although the main idea is to calculate damage on memento (URI-M), this tool can also be used for calculating damage on a live web page (URI-R).  </br>
There are 2 ways to use this tool:
- Online service
- Local service

## Online Service
Online tool can be used by accesing http://memento-damage.cs.odu.edu/. This service is suitable for the purpose of finding the damage of single URI. To use the tool, user just simply type or paste the URI to the damage-check textbox form, and type enter or click check button.

![](https://github.com/erikaris/web-memento-damage/raw/screenshot/pasted%20image%200.png)

The output will be displayed on the result page, on tab ‘summary’. Other tabs in the result page provide the details of the damage according to the resources types: images, stylesheets, javascript, multimedia, and text. Tab ‘screenshot’ provide the screenshot of the URI and tab ‘log’ gives the details of the process that happens during the damage calculation.

![](https://github.com/erikaris/web-memento-damage/raw/screenshot/online-2.png)

### REST API
REST API is provided to facilitate memento-damage calculation is accessed by independent HTTP Client. It is suitable to be used with relatively small number of URIs (e.g. 10 - 100 URIs). Each language should have its own HTTP Client. Here are some examples of accessing memento-damage service using REST API:

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
Local service is used by installing and running Memento Damage tool in user's local machine. This option is suitable for calculating the damage on a myriad number of URIs (e.g. 10.000 URIs).  The web service http://memento-damage.cs.odu.edu/ clearly cannot handle this. Therefore, we provide an option so that users can create the memento damage environment on their own machine.

There are 2 (two) ways to use Memento Damage tool in local machine: using Docker or library. Using docker is recommended since it's result is more consistent.

### Docker
First, install docker in your machine, and make sure docker daemon is started. Please refer to this steps on how to install docker: https://docs.docker.com/engine/getstarted/step_one/#step-2-install-docker. 

Pull the docker image of memento-damage from: erikaris/memento-damage:
```
docker pull erikaris/memento-damage
```

run the container for the image:
```
docker run -i -t -P --name memento-damage erikaris/memento-damage:latest /app/entrypoint.sh
```

Having the memento-damage container running, user can start executing memento-damage tool from within docker container or outside docker container.

#### Inside Container
Attach the container:
```
docker attach memento-damage
```
Or, alternatively, use exec:
```
docker exec -it memento-damage bash
```

Then, start using memento-damage by typing the command:
```
memento-damage [options] <URI>
```

Explore available options by using:
```
memento-damage --help
```

#### Outside Container
We can also executing memento-damage without entering container using:
```
docker exec memento-damage memento-damage [options] <URI>
```
