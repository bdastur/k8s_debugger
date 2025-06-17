#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DDB_Helper: A simpler API to interface with Amazon DynamoDB.

DynamoDB is a fully managed NoSQL Database provided by AWS. It is fast, highly
durable and highly scalable.

A Table is a fundamental data structure in DynamoDB. Tables are schemaless, however
a table requires the items to have atleast one required primary key, which is known
as the partition key. You can also specify an additional sort key. Note that
if you are only using the partition key it must be unique across all items in the
table. If using a sort key the combination of primary key and sort key must be
unique.

Boto3 dynamodb APIs allow operations like get/put/scan/query on items in the
dynamodb Table.

What function does this module serve?
* Simpler interface to get/put/scan/query.
* Set schema validation.
* update item - simplifies modified specific attributes, while ensuring other
  attributes remain the same.
"""

import boto3
import botocore
import logging
import pprint
from boto3.dynamodb.conditions import Key, Attr


def setupLogging(name="dbHelper", logFormat=None, level=logging.WARNING):
    if logFormat is None:
        logformat = "[%(levelname)s %(asctime)s]"\
            "[%(process)d " + name + "] " \
            "%(message)s"
    dateFmt = '%I:%M:%S %p'
    logging.basicConfig(format=logformat, datefmt=dateFmt, level=level)
    # Explicitly set logging levels for other modules to a higher threshold
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)



def getBotoClient(region, profile, service, endpointUrl=None):
    try:
        session = boto3.Session(region_name=region, profile_name=profile)
        client = session.client(service, endpoint_url=endpointUrl)
    except botocore.exceptions.ProfileNotFound as err:
        return None, err

    return client, None


def _unmarshalValue(ddbValue):
    for key, value in ddbValue.items():
        if key.lower() == "s":
            return value
        elif key.lower() == "n":
            try:
                return int(value)
            except ValueError:
                return float(value)
        elif key.lower() == "bool":
            return value
        elif key.lower() == "m":
            data = {}
            for mKey, mValue in value.items():
                data[mKey] = _unmarshalValue(mValue)
            return data
        elif key.lower() == "l":
            data = []
            for item in value:
                data.append(_unmarshalValue(item))
            return data


def unmarshalDynamoDBJson(ddbItem):
    result = {}
    for key, value in ddbItem.items():
        result[key] = _unmarshalValue(value)

    return result


class Table():
    """
    Main class to interface with DynamoDB Tables.

    Example Usage:
    ---------------
    ```
    import awslibs.ddb_helper as ddbhelper

    ddbTable = ddbhelper.Table(region="us-east-1",
                                   profile="dev",
                                   tableName="EmployeeTableV2")
    ```

    **Note**: The specific table should exists.

    Define your item schema.<br></br>
    Defining an item schema will make it easy when performing the get/put/query/scan
    operations on the Table. Unlike the boto3 APIs, you don't specify the
    attributeValues for each operation as the API will use the schema defined
    for the table.
    The Table class APIs can validate that the operations follow the defined
    schema. For update operations, you only need to specify the specific attributes
    you wish to update.
    ```
    itemSchema = [
            {
                "itemName": "Age",
                "itemType": "N"
            },
            {
                "itemName": "FirstName",
                "itemType": "S"
            },
            {
                "itemName": "Level",
                "itemType": "S"
            }
        ]
    ddbTable.setItemSchema(itemSchema)
    ```

    """
    def __init__(self, region="us-east-1", profile=None, tableName=None,
                 endpointUrl=None, debug=False):
        self.tableName = tableName
        self.region = region
        self.profile = profile
        self.endpointUrl = endpointUrl
        self.primaryKey = None
        self.primaryKeyType = None
        self.rangeKey = None
        self.rangeKeyType = None
        self.indexes = []
        self.itemSchema = []
        self._validated = False

        if debug:
            print("Setup debug level")
            level = logging.DEBUG
        else:
            level = logging.WARNING

        setupLogging(level=level)
        self._getTableAttributes()
        logging.debug("Table class initialized")

    def ddbTableIsValidated(self):
        return self._validated

    def _getTableAttributes(self):
        client, errMsg = getBotoClient(self.region, self.profile, "dynamodb",
                                       endpointUrl=self.endpointUrl)
        if client is None:
            logging.warning("Boto3 get client failed %s", errMsg)
            return
        try:
            data = client.describe_table(TableName=self.tableName)
        except botocore.exceptions.ClientError as err:
            print("Failed to describe table %s [%s]" % (self.tableName, err))
            client.close()
            return
        except client.exceptions.ResourceNotFoundException as err:
            print("Failed to describe table %s [%s]" % (self.tableName, err))
            client.close()
            return

        client.close()

        # Populate the Partion key and Sort key for the table.
        #keySchema = data["Table"]["KeySchema"]
        for item in data["Table"]["KeySchema"]:
            if item["KeyType"] == "HASH":
                self.primaryKey = item["AttributeName"]
            elif item["KeyType"] == "RANGE":
                self.rangeKey = item["AttributeName"]

        for item in data["Table"]["AttributeDefinitions"]:
            if item["AttributeName"] == self.primaryKey:
                self.primaryKeyType = item["AttributeType"]
                self.itemSchema.append({"itemName": self.primaryKey,
                                        "itemType": self.primaryKeyType})
            if self.rangeKey and item["AttributeName"] == self.rangeKey:
                self.rangeKeyType = item["AttributeType"]
                self.itemSchema.append({"itemName": self.rangeKey,
                                       "itemType": self.rangeKeyType})

        # Polulate local and global secondary index information.
        localSecondaryIndexes = data["Table"].get("LocalSecondaryIndexes", None)
        if localSecondaryIndexes:
            for index in localSecondaryIndexes:
                obj = {}
                obj["indexType"] = "LocalSecondaryIndex"
                obj["indexName"] = index["IndexName"]
                obj["projectionType"] = index["Projection"]
                for item in index["KeySchema"]:
                    if item["KeyType"] == "RANGE":
                        obj["indexKey"] = item["AttributeName"]
                self.indexes.append(obj)


        globalSecondaryIndexes = data["Table"].get("GlobalSecondaryIndexes", None)
        if globalSecondaryIndexes:
            for index in globalSecondaryIndexes:
                obj = {}
                obj["indexType"] = "GlobalSecondaryIndex"
                obj["indexName"] = index["IndexName"]
                obj["projectionType"] = index["Projection"]
                for item in index["KeySchema"]:
                    if item["KeyType"] == "RANGE":
                        obj["indexKey"] = item["AttributeName"]
                self.indexes.append(obj)

        self._validated = True

    """
    setItemSchema: Set the schema for items to put into table, so that you can
    simplify put items. You can also enable validation to ensure schema is followed.

    itemSchema: [
        {"itemName": "<Value>",
         "itemType": "<Type>"
        },...
    }
    """
    def setItemSchema(self, itemSchema):
        for item in itemSchema:
            self.itemSchema.append(item)


    def putItem(self, item, update=False, validateSchema=True):
        """
        Add an item to the table.

        Parameters:
        ```
        :param item:           dict - The item to add.
        :param update:         bool - Flag to indicate whether to insert new or update item (default False)
        :param validateSchema: bool - Flag to indicate validating schema (default True)
        ```
        Returns:
        ```
        :return result: dict:
                 status: "fail"|"success"
                 errMsg: "String" (in case of failure)
                 result: result/data from the boto3 API.
        ```

        ### Example usage:
        A simple usecase. Adding a new item.
        ```
        item = {"EmployeeId": "001", "FirstName": "Jacob",
                "Campus": "SanJose", "Age": 32, "Level": "L4",
                "Rating": 3, "StartDate": "10/23/2022", "Tenure": 24},
        ret = ddbTable.putItem(item)
        ```

        Update an existing item
        ```
        item = {"EmployeeId": "003", "Age": 52, "FirstName": "Jacob", "Campus": "Fresno", "Level": "L6"}
        ddbTable.putItem(item, update=True)
        ```

        Without validating schema. Here you can pass the item as you would when
        calling the boto3 put_item() API.
        ```
        item = {"EmployeeId": {"S": "0050"}, "Campus": {"S": "Tracy"},
                "Age": {"N": "43"}, "FirstName": {"S": "Jim"},
                "StartDate": {"S": "10-22-2022"}}
        ddbTable.putItem(item, validateSchema=False)
        ```

        """
        result = {}
        if not self._validated:
            print("Put Item Failed. DDB Table not successfully initialized")
            result["status"] = "fail"
            result["errMsg"] = "DDB Table object not initialized"
            return result

        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if client is None:
            print("client is None [%s]" % errmsg)
            result["status"] = "fail"
            result["errMsg"] = errMsg
            return result

        if validateSchema:
            # Check schema.
            schemaItems = [item["itemName"] for item in self.itemSchema]

            itemKeys = list([elem for elem in item.keys()])
            if len(itemKeys) != len(schemaItems):
                print("Invalid Items [%s], Expecting: %s" % (itemKeys, schemaItems))
                client.close()
                result["status"] = "fail"
                result["errMsg"] = "Invalid items [%s], Expecting %s" % (itemKeys, schemaItems)
                return result

            # Convert item in to format dynamodb put_item API understands.
            # example: {"EmployeeId": {"S": "001"}, "Age": {"N": "43"},...}
            ddbItem = {}
            for elem in self.itemSchema:
                itemName = elem['itemName']
                itemType = elem['itemType']
                ddbItem[itemName] = {}
                try:
                    ddbItem[itemName][itemType] = "%s" % item[itemName]
                except KeyError as err:
                    client.close()
                    print("Missing Attribute in item %s" % err)
                    result["status"] = "fail"
                    result["errMsg"] = "Missing attribute in item %s" % err
                    return result
        else:
            ddbItem = item

        try:
            if not update:
                conditionExpression = "attribute_not_exists(%s)" % self.primaryKey
                data = client.put_item(TableName=self.tableName,
                                       Item=ddbItem,
                                       ConditionExpression=conditionExpression,
                                       ReturnConsumedCapacity="TOTAL")
            else:
                data = client.put_item(TableName=self.tableName,
                                       Item=ddbItem,
                                       ReturnConsumedCapacity="TOTAL")
        except botocore.exceptions.ClientError as err:
            client.close()
            print("Put item failed [%s]" % err)
            result["status"] = "fail"
            result["errMsg"] = "Put item failed [%s]" % err
            return result

        client.close()

        result["status"] = "success"
        result["result"] = data
        return result

    def getItem(self, partitionKey, sortKey=None):
        """
        Get an item from the table.

        """
        result = {}
        if not self._validated:
            print("GetItem Failed. DDB Table object not initialized")
            result["status"] = "fail"
            result["errMsg"] = "GetItem Failure. DDB Table object not initialized"
            return result

        ddbItem = {}
        ddbItem[self.primaryKey] = {}
        ddbItem[self.primaryKey][self.primaryKeyType] = partitionKey
        if self.rangeKey and sortKey:
            ddbItem[self.rangeKey] = {}
            ddbItem[self.rangeKey][self.rangeKeyType] = sortKey

        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if not client:
            print("Failed to get botoclient [%s]" % errMsg)
            result["status"] = "fail"
            result["errMsg"] = errMsg
            return result

        try:
            ret = client.get_item(TableName=self.tableName, Key=ddbItem)
        except botocore.exceptions.ParamValidationError as err:
            client.close()
            result["status"] = "fail"
            result["errMsg"] = errMsg
            print("Get Item failed. Error[%s]" % err)
            return result

        client.close()

        item = unmarshalDynamoDBJson(ret["Item"])
        ret["Item"] = item
        result["status"] = "success"
        result["results"] = ret

        return result

    """
    "indexName": "Tenure-index",
            "expressionAttributeValues": {
                ":tenure": {"N": "50"},
                ":campus": {"S": "SanJose"}
            },
            "keyConditionExpression": "Tenure > :tenure AND Campus = :campus"

    findOptions: {
        "Campus": "Campus"
    }
    """
    def queryItems(self, **queryOptions):
        result = {}
        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if not client:
            print("Error in boto client [%s]" % errMsg)
            result["status"] = "fail"
            result["errMsg"] = errmsg
            return result

        keyConditionExpression = queryOptions.get("keyConditionExpression", "")
        expressionAttributeValues = queryOptions.get("expressionAttributeValues", "")
        indexName = queryOptions.get("indexName", None)

        if indexName:
            data = client.query(TableName=self.tableName,
                                IndexName=indexName,
                                KeyConditionExpression=keyConditionExpression,
                                ExpressionAttributeValues=expressionAttributeValues)
        else:
            data = client.query(TableName=self.tableName,
                                KeyConditionExpression=keyConditionExpression,
                                ExpressionAttributeValues=expressionAttributeValues)
        client.close()

        pp = pprint.PrettyPrinter()
        pp.pprint(data)
        items = []
        for item in data["Items"]:
            items.append(unmarshalDynamoDBJson(item))
        data["Items"] = items

        result["status"] = "success"
        result["result"] = data
        return result

    def scanItems(self, **scanOptions):
        """
        scanItems: Scan DynamoDB table.

         Parameters:
        ```
        :param scanOptions:  dict - Scan options.

        scanOptions: {
            "batchSize": Translates to Limit used when invoking the DynamoDB API.,
            "maxScanLimit": Total number of scanned items,
            "expressionAttributeValues": Eg: {":age": {"N": "50"}},
            "filterExpression": Eg: "Age >= :age"

        }

        Refer to [Amazon DynamoDB Expressions/Operators Doc](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html)
        for more information on what filterExpressions can be set.

        Example Usage:
        ---
        ddbTable = ddbhelper.Table(region="us-west-2", profile="dev", tableName="EmployeeTable")


        # Scan all items (Limited by the default max items returned limit).
        scanOptions = {}
        ret = ddbTable.scanItems(**scanOptions)

        # Scan the table and return items where Campus is not SanJose
        scanOptions = {
            "expressionAttributeValues": {":campus": {"S": "SanJose"}},
            "filterExpression": "Campus <> :campus"
        }
        ret = ddbTable.scanItems(**scanOptions)


        """
        result = {}
        result["Count"] = 0
        result["ScannedCount"] = 0
        result["ConsumedCapacityUnits"] = 0
        result["Items"] = []

        batchSize = scanOptions.get("batchSize", 5)
        maxScanLimit = scanOptions.get("maxScanLimit", 200)
        expressionAttributeValues = scanOptions.get("expressionAttributeValues", None)
        filterExpression = scanOptions.get("filterExpression", "")

        if batchSize > maxScanLimit:
            result["status"] = "fail"
            result["errMsg"] = "batchSize %d should be <= maxScanLimit %d" % (batchSize, maxScanLimit)
            return result

        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if client is None:
            result["status"] = "fail"
            result["errMsg"] = errMsg
            return result

        lastEvaluatedKey = None

        while maxScanLimit > 0:
            if lastEvaluatedKey is None:
                try:
                    if not expressionAttributeValues:
                        data = client.scan(TableName=self.tableName, Limit=batchSize,
                                           ReturnConsumedCapacity="TOTAL")
                    else:
                        data = client.scan(TableName=self.tableName, Limit=batchSize,
                                           ReturnConsumedCapacity="TOTAL",
                                           FilterExpression=filterExpression,
                                           ExpressionAttributeValues=expressionAttributeValues)
                except botocore.exceptions.EndpointConnectionError as err:
                    print("Failed to scan [%s]" % err)
                    result["status"] = "fail"
                    result["errMsg"] = err
                    return result
                except botocore.exceptions.ClientError as err:
                    print("Failed to scan [%s]" % err)
                    result["status"] = "fail"
                    result["errMsg"] = err
                    return result
            else:
                if not expressionAttributeValues:
                    data = client.scan(TableName=self.tableName, Limit=batchSize,
                                           ReturnConsumedCapacity="TOTAL",
                                           ExclusiveStartKey=lastEvaluatedKey)
                else:
                    data = client.scan(TableName=self.tableName, Limit=batchSize,
                                       ReturnConsumedCapacity="TOTAL",
                                       FilterExpression=filterExpression,
                                       ExpressionAttributeValues=expressionAttributeValues,
                                       ExclusiveStartKey=lastEvaluatedKey)

            result["Count"] += data["Count"]
            result["ConsumedCapacityUnits"] += data["ConsumedCapacity"]["CapacityUnits"]
            result["ScannedCount"] += data["ScannedCount"]

            maxScanLimit -= batchSize
            for item in data["Items"]:
                result["Items"].append(unmarshalDynamoDBJson(item))

            # Break if we have no other items to scan.
            lastEvaluatedKey = data.get("LastEvaluatedKey", None)
            if lastEvaluatedKey is None:
                break

        client.close()
        result["status"] = "success"
        return result

    def updateItemAttribute(self, partitionKey, sortKey=None, **attributes):
        """
        Update specific attributes for an item, while keeping all other attributes
        intact. For an item with large number of attributes, it is hard to use
        the boto put/update_item API. Even if you are updating a single attribute
        for an item, you would have to specify all the attributes when calling the
        API, otherwise you would update the item with only the attributes you
        passed (AS there is no schma check that the APi performs).

        Parameters:
            partitionKey:  <type> - The partition key for the Table.
            sortKey:       <type> - The sort key if required.
            attributes:    dict   - The attributes to update.

        Returns:
            result {}

        Example usage:
        # Update the Tenure for the Employee item with partition key of sanjose
        # and sort key 001
            attributes = {
                "Tenure": 50
            }
            ret = ddbTable.updateItemAttribute("SanJose", sortKey="001", **attributes)
        """
        ret = self.getItem(partitionKey, sortKey=sortKey)
        if ret["status"] != "success":
            print("Failed to get Item for %s, %s" % (partitionKey, sortKey))
            return ret

        item = ret["results"]["Item"]
        for attr in item.keys():
            if attr in attributes.keys():
                item[attr] = attributes[attr]

        result = {}
        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if client is None:
            print("client is None [%s]" % errmsg)
            result["status"] = "fail"
            result["errMsg"] = errMsg
            return result

        ret = self.putItem(item, update=True, validateSchema=True)
        return ret

    def findAndUpdateItemAttributes(self, **options):
        """
        Find items using query or scan, and update specific attributes.

        Parameters:
          options: dic:
          options = {
              "attributes": {
                  "AttributeKey": "value"  (Attributes to update),
                  ..
              },
              "expressionAttributeValues": {':campus': {'S': 'SanJose'}
              "keyConditionExpression": 'Campus = :campus',
              "filterExpression": "Filter Expression"
          }
          Note: Either keyConditionExpression or filterExpression must be specified.

          Usage Example:
          ----------------
          # Find and replace.
          findOptions = {
              "attributes": {
                  "Tenure": 150
              },
              "expressionAttributeValues": {
                  ":campus": {"S": "SanJose"}
              },
              "keyConditionExpression": "Campus = :campus"
          }
          ret = ddbTable.findAndUpdateItemAttributes(**findOptions)
        """
        print(options)
        #{'attributes': {'Tenure': 150}, 'expressionAttributeValues': {':campus': {'S': 'SanJose'}}, 'keyConditionExpression': 'Campus = :campus'}
        try:
            attributes = options["attributes"]
            expressionAttributeValues = options["expressionAttributeValues"]
        except KeyError as err:
            print("Missing key [%s]" % err)
            return

        keyConditionExpression = options.get("keyConditionExpression", None)
        filterExpression = options.get("filterExpression", None)
        if keyConditionExpression is None and filterExpression is None:
            print("Invalid input. Expecting either filterExpression or keyConditionExpression to be defined")
            return

        if keyConditionExpression:
            queryOptions = {}
            queryOptions["expressionAttributeValues"] = expressionAttributeValues
            queryOptions["keyConditionExpression"] = keyConditionExpression
            if options.get("indexName", None) is not None:
                queryOptions["indexName"] = options["indexName"]
            ret = self.queryItems(**queryOptions)
        else:
            operationType = "scan"

        #
        for item in ret["result"]["Items"]:
            partitionKey = item[self.primaryKey]
            sortKey = item[self.rangeKey]
            ret = self.updateItemAttribute(partitionKey, sortKey=sortKey, **attributes)
            print("Update ret: ", ret)

    def deleteItem(self, partitionKey, sortKey=None):
        result = {}
        if not self._validated:
            print("deleteItem Failed. DDB Table object not initialized")
            result["status"] = "fail"
            result["errMsg"] = "GetItem Failure. DDB Table object not initialized"
            return result

        ddbItem = {}
        ddbItem[self.primaryKey] = {}
        ddbItem[self.primaryKey][self.primaryKeyType] = partitionKey
        if self.rangeKey and sortKey:
            ddbItem[self.rangeKey] = {}
            ddbItem[self.rangeKey][self.rangeKeyType] = sortKey

        client, errMsg = getBotoClient(self.region, self.profile,
                                       "dynamodb", endpointUrl=self.endpointUrl)
        if not client:
            print("Failed to get botoclient [%s]" % errMsg)
            result["status"] = "fail"
            result["errMsg"] = errMsg
            return result

        try:
            ret = client.delete_item(TableName=self.tableName, Key=ddbItem)
        except botocore.exceptions.ParamValidationError as err:
            client.close()
            result["status"] = "fail"
            result["errMsg"] = errMsg
            print("Get Item failed. Error[%s]" % err)
            return result

        client.close()

        result["status"] = "success"
        result["results"] = ret

        return result


    def deleteItems(self, **options):
        result = {}
        expressionAttributeValues = options.get("expressionAttributeValues", None)
        keyConditionExpression = options.get("keyConditionExpression", None)
        filterExpression = options.get("filterExpression", None)

        # If expression Attribute values are not specified we treat it as a scan operation
        # where we want to return all items.
        if not expressionAttributeValues:
            scanOptions = {}
            ret = self.scanItems(**scanOptions)
            if ret["status"] != "success":
                return ret

            items = ret["Items"]
            itemCount = len(items)
            for item in items:
                ret = self.deleteItem(item[self.primaryKey], sortKey=item[self.rangeKey])
                if ret["status"] != "success":
                    logging.error("Failed to delete item [%s]", item)
                    result["status"] = "fail"
                    result["errMsg"] = ret["errMsg"]
                    return result

            result["status"] = "success"
            result["Count"] = itemCount
            return result

        # Query data.
        if keyConditionExpression is not None:
            ret = self.queryItems(**options)
            if ret["status"] != "success":
                return ret

            items = ret["result"]["Items"]
            itemCount = len(items)
            for item in items:
                ret = self.deleteItem(item[self.primaryKey], sortKey=item[self.rangeKey])
                if ret["status"] != "success":
                    logging.error("Failed to delete item [%s]", item)
                    result["status"] = "fail"
                    result["errMsg"] = ret["errMsg"]
                    return result

            result["status"] = "success"
            result["Count"] = itemCount
            return result

        # Scan with filter expression.
        if filterExpression:
            ret = self.scanItems(**options)
            if ret["status"] != "success":
                return ret

            items = ret["Items"]
            itemCount = len(items)
            for item in items:
                ret = self.deleteItem(item[self.primaryKey], sortKey=item[self.rangeKey])
                if ret["status"] != "success":
                    logging.error("Failed to delete item [%s]", item)
                    result["status"] = "fail"
                    result["errMsg"] = ret["errMsg"]
                    return result

            result["status"] = "success"
            result["Count"] = itemCount
            return result









"""
ddbScanTable: The API is a wrapper on top of dynamodb Scan() API.
parameters:
    tableName:   string - Name of the table to scan.
    region:      string - AWS region
    profile:     string - Profile as specified in AWS credentials file.
    apiType:     string - Whether to use DynamoDB resource API or Boto3 client.
                          options (client|resource)
    scanOptions: dict   - scan options.
        batchLimit: batch count - this translates to Limit in Scan operation
        limit: Total items to scan.
        filterExpression: Filter expression as per dynamodb API.
        expressionAttributeValues: Dynamodb attribute values (for client API scan)

"""
def ddbScanTable(tableName, region, profile,
                 apiType="resource", **scanOptions):
    validApiTypes = ["client", "resource"]
    result = {}

    if apiType == "client":
        return ddbScanClient(tableName, region, profile, **scanOptions)
    elif apiType == "resource":
        return ddbScanResource(tableName, region, profile, **scanOptions)
    else:
        result["status"] = "fail"
        result["errMsg"] = "Invalid api type %s (supported: %s)" % \
                            (apiType, validApiTypes)
        return result



"""

    scanOptions: {
        "batchLimit": Batch count - this translate to limit
        "limit": This translates to total items you want to scan,
        "filterExpression": Filter expression as per dynamodb API.
        "postFilterExpression":  Apply Filters on scanned items.
    }
"""
def ddbScanResource(tableName, region, profile, endpointUrl=None, **scanOptions):
    session = boto3.Session(profile_name=profile, region_name=region)

    dynamoDB = session.resource("dynamodb", endpoint_url=endpointUrl)
    table = dynamoDB.Table(tableName)

    batchLimit = scanOptions.get("batchLimit", 5)
    limit = scanOptions.get("limit", 10)
    filterExpression = scanOptions.get("filterExpression", None)

    result = {}
    result["Count"] = 0
    result["ScannedCount"] = 0
    result["ConsumedCapacityUnits"] = 0
    result["Items"] = []

    lastEvaluatedKey = None
    while limit > 0:
        try:
            if lastEvaluatedKey is None:
                data = table.scan(FilterExpression=filterExpression,
                                  ReturnConsumedCapacity="TOTAL",
                                  Limit=batchLimit)
            else:
                data = table.scan(FilterExpression=filterExpression,
                                  ReturnConsumedCapacity="TOTAL",
                                  ExclusiveStartKey=lastEvaluatedKey,
                                  Limit=batchLimit)

            result["Count"] += data["Count"]
            result["ConsumedCapacityUnits"] += data["ConsumedCapacity"]["CapacityUnits"]
            result["ScannedCount"] += data["ScannedCount"]

            result["Items"].extend(data["Items"])
        except botocore.exceptions.ClientError as err:
            print("Failed to scan table %s [%s]" % (tableName, err))
            result["status"] = "fail"
            result["errMsg"] = err
            return result
        except botocore.exceptions.EndpointConnectionError as err:
            print("Failed to scan table %s [%s]" % (tableName, err))
            result["status"] = "fail"
            result["errMsg"] = err
            return result

        limit -= batchLimit

        # We check for LastEvaluatedKey to see if we have additional
        # data from the API that we can query.
        # Break if we have no other items to scan.
        lastEvaluatedKey = data.get("LastEvaluatedKey", None)
        if lastEvaluatedKey is None:
            break

    result["status"] = "success"
    return result


def ddbScanClient(tableName, region, profile, endpointUrl=None, **scanOptions):
    result = {}
    result["Count"] = 0
    result["ScannedCount"] = 0
    result["ConsumedCapacityUnits"] = 0
    result["Items"] = []

    client, errMsg = getBotoClient(region, profile,
                                   "dynamodb", endpointUrl=endpointUrl)
    if client is None:
        result["status"] = "fail"
        result["errMsg"] = errMsg
        return result


    batchLimit = scanOptions.get("batchLimit", 5)
    limit = scanOptions.get("limit", 10)
    expressionAttributeValues = scanOptions.get("expressionAttributeValues", None)
    filterExpression = scanOptions.get("filterExpression", "")

    print(type(expressionAttributeValues), expressionAttributeValues)
    print(type(filterExpression), filterExpression)

    lastEvaluatedKey = None

    while limit > 0:
        if lastEvaluatedKey is None:
            try:
                data = client.scan(TableName=tableName, Limit=batchLimit,
                                   ReturnConsumedCapacity="TOTAL",
                                   FilterExpression=filterExpression,
                                   ExpressionAttributeValues=expressionAttributeValues)
            except botocore.exceptions.EndpointConnectionError as err:
                print("Failed to scan [%s]" % err)
                result["status"] = "fail"
                result["errMsg"] = err
                return result
            lastEvaluatedKey = data["LastEvaluatedKey"]
        else:
            data = client.scan(TableName=tableName, Limit=batchLimit,
                               ReturnConsumedCapacity="TOTAL",
                               FilterExpression=filterExpression,
                               ExpressionAttributeValues=expressionAttributeValues,
                               ExclusiveStartKey=lastEvaluatedKey)

        result["Count"] += data["Count"]
        result["ConsumedCapacityUnits"] += data["ConsumedCapacity"]["CapacityUnits"]
        result["ScannedCount"] += data["ScannedCount"]

        limit -= batchLimit
        for item in data["Items"]:
            result["Items"].append(unmarshalDynamoDBJson(item))

    client.close()
    pp = pprint.PrettyPrinter()
    pp.pprint(result)
    result["status"] = "success"
    return result









