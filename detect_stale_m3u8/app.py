import os
import json
import urllib.parse
import m3u8
import boto3
from email.utils import parsedate_to_datetime
from datetime import datetime
import time

#instantiate s3 client
s3 = boto3.client("s3")

# set multiple of target_duration to be considered stale. For example, if target_duration is 6, playlist must be 9s or older to be considered stale
multiple = float(os.environ['TARGET_DURATION_MULTIPLE'])

def lambda_handler(event, context):

    # Get the m3u8 object from s3
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        working_file = s3.get_object(Bucket=bucket, Key=key)
        lastmodified = int(working_file["LastModified"].strftime("%s"))
        playlist = m3u8.loads(working_file["Body"].read().decode("utf-8"))
    except Exception as e:
        print(e)
        print('Error getting or parsing playlist {} from bucket {}'.format(key, bucket))
        raise e
        
    def getLastModified(bucket, key):
        return int(s3.head_object(Bucket=bucket, Key=key)["LastModified"].strftime("%s"))
        
    def getSecondsTo(nextCheckTime):
        return max(0, nextCheckTime - (int(datetime.now().strftime("%s"))))
        
    def getStaleTime(playlist):
        return lastmodified + (playlist.target_duration * multiple)
        
    def checkStale(obj, key):
        
        #sleep script until the time the m3u8 playlist is considered stale
        staleTime = getStaleTime(playlist)
        secondsToStaleTime = getSecondsTo(staleTime)
        print('M3u8 playlist is considered stale unless updated by {} sleeping for {} seconds'.format(staleTime, secondsToStaleTime))
        time.sleep(secondsToStaleTime)
        
        #after sleep, check if playlist m3u8 has been updated with new by comparing last modified times
        if getLastModified(bucket, key) > lastmodified:
            return False
        else:
            return True
    
    # set default response as no change
    statusCode = 304
    body = 'No Change'
    
    #detect if m3u8 is top level/primary/variant and ignore if so
    if playlist.is_variant:
        print('{} is primary'.format(key))
    #detect if m3u8 contains an ENDLIST tag ignore if so
    elif playlist.is_endlist:
        print('{} contains #EXT-X-ENDLIST tag'.format(key))
    #check if playlist is stale and delete if so
    else:
        if checkStale(bucket, key):
            try:
                s3.delete_object(Bucket=bucket, Key=key)
                print('*STALE PLAYLIST DETECTED* Deleting {} from {} with last modified time of {}'.format(key, bucket, lastmodified))
                statusCode = 202
                body = 'Object Deleted'
            except Exception as e:
                print(e)
                print('Error deleting playlist {} from bucket {}'.format(key, bucket))
                raise e   
        
    return {
        'statusCode': statusCode,
        'body': json.dumps(body)
    }
