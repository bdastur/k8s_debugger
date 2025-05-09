#################################################################
# Makefile to help build the Docker container.
# Pre-req:
# - Install GNU make
#
# Example Usages:
# ------------------
#
# - Build the image
# make profile=default build
#
# - Test variables.
# make test
#
# - Publish image
# make profile=default publish
#
# - Run the image locally.
# make run
#
# - Run the image with interactive (exec into the shell)
# make  run-it
#
# Notes to self:
# @echo - is silent echo. Displays the output only once.
# <var> ?= <var? - The ?= allows setting default value if not passed through commandline.
#
#################################################################
profile ?= brd3
region ?= us-east-1
account  = $(shell aws sts get-caller-identity --profile ${profile} --region ${region} --output text | awk -F" " '{print $$1}')
ecrRepo=${account}.dkr.ecr.${region}.amazonaws.com

imageName=k8s_mcp_client
imageVersion=latest
container=k8s_mcp_client


test:
	@echo " ------------ variables -------------"
	@echo "Profile: ${profile}"
	@echo "Region: ${region}"
	@echo "Account: ${account}"
	@echo "ECR Repository: ${ecrRepo}"
	@echo "--------------------------------------"


.PHONY: test

build: Dockerfile test
	mkdir -p .stage
	cp -R ../commonlibs ./.stage/commonlibs
	docker build -t $(imageName):${imageVersion} .
	rm -rf .stage

build-nocache: Dockerfile
	mkdir -p .stage
	cp -R ../commonlibs ./.stage/commonlibs
	docker build --no-cache -t $(imageName):${imageVersion} .
	rm -rf .stage

run-it:
	docker rm -f ${container}
	docker run -it --network mcpnetwork -e profile=${profile} -e region=${region} --volume ~/.aws:/root/.aws --volume /tmp:/tmp --name ${container} ${imageName} /bin/bash

run:
	docker rm -f ${container}
	docker run --detach --network mcpnetwork -e profile=${profile} -e region=${region} --volume ~/.aws:/root/.aws --volume /tmp:/tmp --name ${container} ${imageName}

tag-ecr:
	docker tag ${imageName}:${imageVersion} ${ecrRepo}/${imageName}:${imageVersion}

publish:
	aws ecr get-login-password --profile ${profile} --region ${region} | docker login --username AWS --password-stdin ${ecrRepo}
	docker tag ${imageName}:${imageVersion} ${ecrRepo}/${imageName}:${imageVersion}
	docker push ${ecrRepo}/${imageName}:${imageVersion}

help:
	@echo "Commands: build, run-it, run, tag-ecr, publish"
	@echo "Example usage: make profile=brd4 build"


