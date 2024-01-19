#!/usr/bin/env python3

import requests

import pandas as pd
import boto3
import uuid
import datetime
from boto3.dynamodb.conditions import Attr


# SSM Parameter names
ssm_base_api_url = "/data/api/lambda/ods/domain"
ssm_param_id = "/data/api/lambda/client_id"
ssm_param_sec = "/data/api/lambda/client_secret"

# ODS code file
odscode_file_path = "./ODS_Codes.xlsx"

# DynamoDB table name
dynamodb_table_name = "locations"


def lambda_handler(event, context):
    print("Fetching organizations data.")
    fetch_organizations()
    print("Fetching Y organizations data.")
    fetch_y_organizations()


# Get parameters from store
def get_ssm(name):
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    return response


def get_api_token():
    token_api_endpoint = get_ssm(ssm_base_api_url)
    token_api_endpoint += (
        "//authorisation/auth/realms/terminology/protocol/openid-connect/token"
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "Keep-alive",
    }

    data = {
        "grant_type": "client_credentials",
        "client_id": get_ssm(ssm_param_id),
        "client_secret": get_ssm(ssm_param_sec),
    }

    response = requests.post(url=token_api_endpoint, headers=headers, data=data)
    token = response.json().get("access_token")

    return token


def get_headers():
    token = get_api_token()
    headers = {"Authorization": "Bearer " + token}
    return headers


def read_ods_api(api_endpoint, headers, params):
    try:
        response = requests.get(api_endpoint, headers=headers, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            response_data = response.json()
            return response_data
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def capitalize_line(line):
    return line.title()


def capitalize_address_item(address_item):
    capitalized_item = {}

    for key, value in address_item.items():
        if key == "line" and isinstance(value, list):
            capitalized_item[key] = [capitalize_line(line) for line in value]
        elif key in ["city", "district", "country"]:
            capitalized_item[key] = value.title()
        elif key == "postalCode":
            capitalized_item[key] = value
        elif key != "extension":
            capitalized_item[key] = value

    return capitalized_item


def process_organizations(organizations):
    processed_data = []
    random_id = str(uuid.uuid4().int)[0:16]
    current_datetime = datetime.datetime.now()
    now_time = current_datetime.strftime("%d-%m-%Y %H:%M:%S")
    for resvars in organizations:
        org = resvars.get("resource")
        if org.get("resourceType") == "Organization":
            try:
                uprn = (
                    org.get("address")[0]
                    .get("extension")[0]
                    .get("extension")[1]
                    .get("valueString")
                )
            except Exception:
                uprn = "NA"

            capitalized_address = [
                capitalize_address_item(address_item)
                for address_item in org.get("address", [])
                if isinstance(address_item, dict)
            ]

            processed_attributes = {
                "id": random_id,
                "lookup_field": org.get("id"),
                "active": "true",
                "name": org.get("name").title(),
                "Address": capitalized_address,
                "createdDateTime": now_time,
                "createdBy": "Admin",
                "modifiedBy": "Admin",
                "modifiedDateTime": now_time,
                "UPRN": uprn,
                "position": {"longitude": "", "latitude": ""},
                "managingOrganization": "",
            }
            if uprn == "NA":
                processed_attributes.pop("UPRN")
            processed_data.append(processed_attributes)
    return processed_data


def write_to_dynamodb(table_name, processed_data):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    for item in processed_data:
        identifier_value = item.get("lookup_field", {})

        # Check if the identifier already exists in DynamoDB
        if data_exists(table, identifier_value) is False:
            # If the data doesn't exist, insert it into DynamoDB
            table.put_item(Item=item)

    # Call the function to update records in DynamoDB based on lookup_field
    update_records()


def data_exists(table, identifier_value):
    response = table.scan(FilterExpression=Attr("lookup_field").eq(identifier_value))
    if response.get("Items") == []:
        return False
    else:
        return True


def update_records():
    dynamodb = boto3.resource("dynamodb")
    org_table = dynamodb.Table("organisations")
    locations_table = dynamodb.Table("locations")
    org_response = org_table.scan()
    locations_response = locations_table.scan()
    org_items = org_response.get("Items")
    locations_items = locations_response.get("Items")

    for locations_item in locations_items:
        locations_id = locations_item.get("id")
        if locations_item.get("managingOrganization") == "":
            locations_lookup_field_value = locations_item.get("lookup_field")

            if locations_lookup_field_value:
                for org_item in org_items:
                    org_identifier_value = org_item.get("identifier", {}).get(
                        "value", ""
                    )
                    if org_identifier_value == locations_lookup_field_value:
                        org_id = org_item.get("id")
                        locations_table.update_item(
                            Key={"id": locations_id},
                            UpdateExpression="SET managingOrganization = :val",
                            ExpressionAttributeValues={":val": org_id},
                        )


def read_excel_values(file_path):
    # Read values from the Excel file
    excel_data = pd.read_excel(file_path)
    param1_values = excel_data["ODS_Codes"].tolist()

    # # Hardcoded values for param2
    param2_value = [
        "OrganizationAffiliation:primary-organization",
        "OrganizationAffiliation:participating-organization",
    ]

    # list of dictionaries with the desired format
    params = [
        {"primary-organization": val, "_include": param2_value} for val in param1_values
    ]

    return params


# def write_to_json(output_file_path, processed_data):
#     import json
#     with open(output_file_path, "a") as output_file:
#         json.dump(processed_data, output_file, indent=2)
#         output_file.write("\n")


# # Iterate over Excel values and make API requests
def fetch_organizations():
    api_endpoint = get_ssm(ssm_base_api_url)
    api_endpoint += "/fhir/OrganizationAffiliation?active=true"
    failed_to_fetch = "Failed to fetch data from the ODS API."
    headers = get_headers()
    odscode_params = read_excel_values(odscode_file_path)
    for odscode_param in odscode_params:
        # Call the function to read from the ODS API and write to the output file
        response_data = read_ods_api(api_endpoint, headers, params=odscode_param)

        # Process and load data to json file
        if response_data:
            organizations = response_data.get("entry", [])
            processed_data = process_organizations(organizations)
            write_to_dynamodb(dynamodb_table_name, processed_data)
            # output_file_path = "./location.json"
            # write_to_json(output_file_path, processed_data)

        else:
            print(failed_to_fetch)

    if response_data:
        print("Data fetched successfully.")

    else:
        print(failed_to_fetch)


# fetch Y code organizations
def fetch_y_organizations():
    api_endpoint_y = get_ssm(ssm_base_api_url)
    api_endpoint_y += "/fhir/Organization?active=true"
    failed_to_fetch = "Failed to fetch data from the ODS API."
    params_y = {"type": "RO209"}
    headers = get_headers()
    y_response_data = read_ods_api(api_endpoint_y, headers, params=params_y)

    # Process and load data to json file
    if y_response_data:
        organizations = y_response_data.get("entry", [])
        processed_data = process_organizations(organizations)
        write_to_dynamodb(dynamodb_table_name, processed_data)
        # output_file_path = "./location.json"
        # write_to_json(output_file_path, processed_data)

    else:
        print(failed_to_fetch)

    if y_response_data:
        print("Y Data fetched successfully.")

    else:
        print(failed_to_fetch)