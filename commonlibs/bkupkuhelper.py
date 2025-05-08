#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import kubernetes
import yaml
import kubernetes.client as kclient
import kubernetes.utils as kutils
import kubernetes.dynamic as kdynamic
import commonlibs.render as render


#######################################################################
# Setup Logging.
#######################################################################
def get_logger(level=logging.INFO,
               name="Default",
               msg_format:str = '[%(asctime)s %(levelname)s]:  %(message)s',
               date_format: str = '%m-%d %H:%M', 
               output_file_name: str = './output.log'):

    print("Get Logger: %s" % name)
    logger = logging.getLogger(name)

    logging.basicConfig(level=level,
                        format=msg_format,
                        datefmt=date_format,
                        filename=output_file_name,
                        filemode='w')

    if logger.hasHandlers():
        logger.handlers.clear()

    # Set console message format. Can be the same.
    consoleMsgFormat:str = msg_format

    console = logging.StreamHandler()
    #avoid logs below INFO serity to standard out
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(consoleMsgFormat))
    # add the handler to the root logger
    logger.addHandler(console)

    return logger


class KuPods():
    def __init__(self, verbose=True):
        logLevel = logging.WARN
        if verbose:
            logLevel = logging.INFO

        self.logger = get_logger(name="KuPods", level=logLevel)
        self.kuHelper = KuHelper(verbose=True)


    def _parsePodDetails(self, podDetail):
        """
        For intidivual pod within a Pod list or a specific pod, parse and return
        a normalized struck after parsing the podDetails.
        """
        obj = {}
        namespace = podDetail["metadata"]["namespace"]

        obj["kind"] = podDetail["kind"]
        obj["metadata"] = {}
        obj["metadata"]["labels"] = podDetail["metadata"]["labels"]
        obj["metadata"]["name"] = podDetail["metadata"]["name"]
        obj["metadata"]["namespace"] = namespace
        obj["metadata"]["resourceVersion"] = podDetail["metadata"]["resourceVersion"]


        obj["spec"] = {}
        obj["total_container_count"] = 0

        obj["containers"] = []
        for container in podDetail["spec"]["containers"]:
            obj2 = {}
            obj2["name"] = container["name"]
            obj2["image"] = container["image"]
            obj2["imagePullPolicy"] = container["imagePullPolicy"]
            obj2["resources"] = container["resources"]
            obj2["ports"] = container.get("ports", [])
            obj2["volumeMounts"] = container["volumeMounts"]

            obj["containers"].append(obj2)
            obj["total_container_count"] += 1


    def getPodsInformation(self, podName=None, namespace=None):
        results = {}
        print("BRD: get pod info: ", podName, namespace)

        ret = self.kuHelper.getResource(resourceType="pod", resourceName=podName, namespace=namespace)

        print("BRD: ret: ", ret)

        results["kind"] = ret["kind"]
        results["items"] = []
        results["summary"] = {
            "total_pod_count": 0,
            "pods_count_by_namespace": {}
        }

        if ret["kind"] == "Pod":
            podDetails = self._parsePodDetails(ret) 
            results["items"].append(podDetails)
            results["total_pod_count"] = 1
            namespace = ret["metadata"]["namespace"]
            print("BRD: namespace: ", namespace)
            results["summary"]["pods_count_by_namespace"][namespace] = 1

            return results

        perNamespaceCount = {}
        for item in ret["items"]:
            namespace = item["metadata"]["namespace"]

            obj = {}

            obj["kind"] = item["kind"]
            obj["metadata"] = {}
            obj["metadata"]["labels"] = item["metadata"]["labels"]
            obj["metadata"]["name"] = item["metadata"]["name"]
            obj["metadata"]["namespace"] = namespace 
            obj["metadata"]["resourceVersion"] = item["metadata"]["resourceVersion"]

            obj["spec"] = {}
            obj["total_container_count"] = 0

            obj["containers"] = []
            for container in item["spec"]["containers"]:
                obj2 = {}
                obj2["name"] = container["name"]
                obj2["image"] = container["image"]
                obj2["imagePullPolicy"] = container["imagePullPolicy"]
                obj2["resources"] = container["resources"]
                obj2["ports"] = container.get("ports", [])
                obj2["volumeMounts"] = container["volumeMounts"]

                obj["containers"].append(obj2)
                obj["total_container_count"] += 1

            try:
                perNamespaceCount[namespace] += 1
            except KeyError:
                perNamespaceCount[namespace] = 1

            results["items"].append(obj)
            results["summary"]["total_pod_count"] += 1

        results["summary"]["pods_count_by_namespace"] = perNamespaceCount

        return results




class KuHelper():
    def __init__(self, verbose=True):

        logLevel = logging.WARN
        if verbose:
            logLevel = logging.INFO

        self.logger = get_logger(name="Kuhelper", level=logLevel) 
        self._authenticate()
        self.client = kclient.ApiClient()

    def _authenticate(self):
        kubernetes.config.load_config()

    def _getResourceKind(self, resourceType: str) -> str:
        """Get resource kind from type"""
        kinds = {
            'pod': 'Pod',
            'node': "Node",
            'deployment': 'Deployment',
            'service': 'Service',
            'ingress': 'Ingress',
            'configmap': 'ConfigMap',
            'secret': 'Secret',
            'namespace': 'Namespace',
            'persistentvolumeclaim': 'PersistentVolumeClaim',
            'persistentvolume': 'PersistentVolume',
            'statefulset': 'StatefulSet',
            'daemonset': 'DaemonSet',
            'job': 'Job',
            'cronjob': 'CronJob',
            'networkpolicy': 'NetworkPolicy',
            'resourcequota': 'ResourceQuota'
        }
        return kinds.get(resourceType.lower(), resourceType.capitalize())

    def _getApiVersion(self, resourceType: str) -> str:
        """Get API version for resource type"""
        apiVersions = {
            'pod': 'v1',
            'node': 'v1',
            'deployment': 'apps/v1',
            'service': 'v1',
            'ingress': 'networking.k8s.io/v1',
            'configmap': 'v1',
            'secret': 'v1',
            'namespace': 'v1',
            'persistentvolumeclaim': 'v1',
            'persistentvolume': 'v1',
            'statefulset': 'apps/v1',
            'daemonset': 'apps/v1',
            'job': 'batch/v1',
            'cronjob': 'batch/v1',
            'networkpolicy': 'networking.k8s.io/v1',
            'resourcequota': 'v1'
        }
        return apiVersions.get(resourceType.lower(), 'v1')

    def createResourceFromResourceSpec(self, resourceSpec):
        try:
            ret = kutils.create_from_dict(self.client, resourceSpec)
        except kutils.FailToCreateError as err:
            self.logger.error("Failed to create namespace [%s]", err)
            return None

        return ret

    def createResourceFromTemplate(self, template, **spec):
        data = json.loads((render.renderJ2TemplateFile(template, "..", **spec)))
        self.logger.info(data)

        try:
            ret = kutils.create_from_dict(self.client, data)
        except kutils.FailToCreateError as err:
            self.logger.error("Failed to create namespace [%s]", err)
            return None

        return ret

    def getResource(self,
                    resourceType:str = None,
                    resourceName:str = None,
                    namespace:str =None):
        """
        Get the Kubernetes resource.
        """
        assert resourceType is not None

        dynamicClient = kdynamic.DynamicClient(self.client)

        resourceKind = self._getResourceKind(resourceType)
        apiVersion = self._getApiVersion(resourceType)

        resource = dynamicClient.resources.get(
            api_version=apiVersion,
            kind=resourceKind
        )

        try:
            if namespace:
                if resourceName:
                    ret = resource.get(name=resourceName, namespace=namespace)
                else:
                    ret = resource.get(namespace=namespace)
            else:
                if resourceName:
                    ret = resource.get(name=resourceName)
                else:
                    ret = resource.get()
        except kclient.rest.ApiException as e:
            if e.status == 404:
                self.logger.warning(
                    f"Resource '{resourceName}' of type '{resourceType}' "
                    f"{'in namespace ' + namespace if namespace else ''} does not exist."
                )
                return None
            else:
                raise

        # Return a dict.
        return ret.to_dict()

    def deleteResource(self,
                       resourceType:str,
                       resourceName:str,
                       namespace=None,
                       force:bool=False):
        #client = kclient.ApiClient()

        dynamicClient = kdynamic.DynamicClient(self.client)

        resourceKind = self._getResourceKind(resourceType)
        apiVersion = self._getApiVersion(resourceType)

        resource = dynamicClient.resources.get(
            api_version=apiVersion,
            kind=resourceKind
        )

        ret = self.getResource(resourceType, resourceName, namespace)
        if ret is None:
            return

        # Delete options
        deleteOptions = kclient.V1DeleteOptions(
            propagation_policy="Foreground",
            grace_period_seconds=5)


        # Delete the resource
        if namespace:
            resource.delete(
                name=resourceName,
                namespace=namespace,
                body=deleteOptions
            )
        else:
            resource.delete(
                name=resourceName,
                body=deleteOptions
            )

        self.logger.info(
            f"Resource '{resourceName}' of type '{resourceType}' "
            f"{'in namespace ' + namespace if namespace else ''} deletion initiated."
        )

    def createNamespace(self, **spec):
        """
        Create a Namespace.

        @params:
        spec: dict - Specification for the namespace creation.

        Example Spec:
          {
              "name": <name>,
              "labels": {
                "foo": "value",
                "bar": "value"
              },
              "annotations": {
                "afoo": "value",
                "abar": "value"
              }
          }
        """
        namespaceTemplate = "kutemplates/namespace.json.j2"

        ret = self.createResourceFromTemplate(namespaceTemplate, **spec)
        return ret


    def createResourceQuota(self, **spec):
        """
        Create Resource Quotas

        @params:
        spec:
        {
          "name": <resource quota name>,
          "namespace": <namespace to be applied to>
          "requests": {
             "cpu": 2,
             "memory": 2Gi
          },
          "limits": {
             "cpu": 4,
             "memory": 4Gi
          },
          "pods": 10
        }

        """
        resourceQuotaTemplate = "kutemplates/resourceQuota.json.j2"

        ret = createResourceFromTemplate(resourceQuotaTemplate, **spec)
        return ret

    def _addMetadataLabels(self, resourceSpecObject, **spec):
        """
        Add the metadata section to the resource.
        """
        metadata = {
            "labels": {
                "createdBy": "KuBot"
            },
            "annotations": {
                "createdBy": "KuBot"
            }
        }


"----------------------------------------------------------"


