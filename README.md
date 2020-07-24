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

There are 2 (two) ways to use Memento Damage tool in local machine: using Docker or library. Using docker is recommended since user does not need to worry about system dependencies.

### Docker
First, install docker in your machine, and make sure docker daemon is started. Please refer to this steps on how to install docker: https://docs.docker.com/engine/getstarted/step_one/#step-2-install-docker. 

Pull the docker image of memento-damage from: erikaris/memento-damage:
```
docker pull erikaris/memento-damage
```

Run the container for the image:
```
docker run -i -t -P --name memento-damage erikaris/memento-damage:latest /app/entrypoint.sh

```
Then, user can start executing memento-damage tool from within docker container or outside docker container.

#### Inside Container
Attach the container:
```
docker attach memento-damage
```
Alternatively, use exec:
```
docker exec -it memento-damage bash
```

Then, start using memento-damage by typing the command:
```
memento-damage [options] <URI>
```

Explore available options by typing:
```
memento-damage --help
```

#### Outside Container
We can also executing memento-damage without entering container using:
```
docker exec memento-damage memento-damage [options] <URI>
```

### Library
Using library is relatively similar to using docker. The installation process is much simpler and faster than the docker version. But user has to ensure that all the requirements (phantomjs 2.xx and python 2.7) are installed on their machines.  <br />
Download the latest library version from https://github.com/oduwsdl/web-memento-damage/tree/master/dist. <br />
Install the library using command:  
```
sudo pip install memento-damage-x.x.x.tar.gz
```
Start using the tool by typing the command ‘memento-damage’, which is similar to that of the docker version. 


