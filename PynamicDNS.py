import argparse
import json
import sys

import boto3
import requests


def parse_arguments():
    parser=argparse.ArgumentParser(
        description='''The purpose of this script is to change an AWS DNS record to match your current public ip''')
    parser.add_argument('DNS_RECORD', type=str, nargs='?', 
        help='''Route 53 DNS record, for example pynamicdns.tynick.com
                Warning! the record must already exist!''')
    parser.add_argument('HOSTED_ZONE_ID', type=str, nargs='?', help='Route 53 Hosted zone ID, for example X0XXXXXX000X0')
    parser.add_argument('-c', '--config', help='Path to a json file with records to update')
    args=parser.parse_args()

    if args.DNS_RECORD and args.HOSTED_ZONE_ID:
        return [{'DNS_RECORD': args.DNS_RECORD,'HOSTED_ZONE_ID': args.HOSTED_ZONE_ID}]
    if args.config:
        try:
            with open(args.config) as json_file:
                config_json = json.load(json_file)
        except:
            print('Supplied json file is not valid!')
            exit()
        return config_json
    parser.print_help()
    exit()

records = parse_arguments()

try:
    client = boto3.client('route53')
except:
    print('FAILED - Check that boto3 is installed and that you populated your ~/.aws/ credentials and config files')
    exit()

# get your public ip
def get_public_ip():
    public_ip = requests.get('https://api.ipify.org').text
    return public_ip

# get the value of your DNS record from Route53
def get_record_value(record):
    # attempt to get value of DNS record
    try:
        response = client.test_dns_answer(
            HostedZoneId=record['HOSTED_ZONE_ID'],
            RecordName=record['DNS_RECORD'],
            RecordType='A',
        )
    except:
        response = 'FAILED'

    try:
        # make sure we got a 200 from aws
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            # parse out the value and assume there is only 1 value in the list
            response = response['RecordData'][0]
        else:
            response = 'FAILED'
    except:
        # this means response['ResponseMetadata']['HTTPStatusCode'] didnt exist
        response = 'FAILED - Check HOSTED_ZONE_ID and DNS_RECORD in AWS'
    return response

def change_record_value(public_ip, record):
    # attempt to change the value of the Route53 DNS record
    try:
        response = client.change_resource_record_sets(
            HostedZoneId=record['HOSTED_ZONE_ID'],
            ChangeBatch={
                'Comment': 'PynamicDNS Change',
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': record['DNS_RECORD'],
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [
                                {
                                    'Value': public_ip
                                },
                            ],
                        }
                    },
                ]
            }
        )
    except:
        response = 'FAILED'

    # make sure we got a 200 from aws
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        response = 'DNS CHANGE SUCCESSFUL'
    else:
        # something went wrong and response['ResponseMetadata']['HTTPStatusCode'] didnt exist. 
        response = 'FAILED'

    return response

public_ip = get_public_ip()
for record in records:
    record_value = get_record_value(record)
    # this just formats some output and assumes DNS_RECORD+2 is more chars than 'Public IP: '
    padding = len(record['DNS_RECORD']) + 2 - len('Public IP: ')
    print('---------------------------')
    print('Public IP: {0}{1}'.format(padding * ' ', public_ip))
    print('{0}: {1}'.format(record['DNS_RECORD'], record_value))
    print('---------------------------')

    # if IP changed, change the Route53 record
    # if not, do nothing
    if public_ip != record_value:
        print("DNS VALUE DOES NOT MATCH PUBLIC IP")
        # change record value to current public_ip
        print(change_record_value(public_ip, record))
        print('Check https://console.aws.amazon.com/route53/home#resource-record-sets:{0} to verify your DNS change'.format(record['HOSTED_ZONE_ID']))
    else:
        print("NO CHANGE NEEDED")
