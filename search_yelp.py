import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime
# import yelp
from yelp.client import Client


yelp_client_id = os.environ['YELP_CLIENT_ID']
yelp_api_key = os.environ['YELP_API_KEY']

client = Client(yelp_api_key)

# define globally?
search_headers = {'Authorization': 'Bearer %s' % yelp_api_key}


def business_search_yelp(search_params):
    search_url = 'https://api.yelp.com/v3/businesses/search'

    response = requests.get(search_url, params=search_params, headers=search_headers)
    # print(response.request.url)
    # print(response.text)

    # proceed only if the status code is 200
    if response.status_code == 200:
        # search_results_json = json.loads(response.text)
        search_results_df = pd.DataFrame.from_dict(response.json()['businesses'])  # TODO: Keep this as json/dict for now (don't make into DF)
        return search_results_df

    else:
        print('Non-200 status code: {}'.format(response.status_code))
        return None  # TODO: ???


def loop_offset_search(search_params):
    search_dfs_list = [business_search_yelp(search_params)]
    offset_mult = 1
    while search_dfs_list[-1].shape[0] == 50:
        print('---------------------- Looping through results... ----------------------')
        print('More data available...most recent scraped data # rows:', search_dfs_list[-1].shape[0])
        print('# dfs in list:', len(search_dfs_list))
        search_params['offset'] = 50 * offset_mult
        print('# results:', search_params['offset'])
        search_dfs_list.append(business_search_yelp(search_params))
        offset_mult += 1

    all_search_results_df = pd.concat(search_dfs_list)
    # TODO: Dedupe DF just in case there truly are exactly 50 results?

    return all_search_results_df


def business_details_yelp(yelp_id):
    business_id_url = "https://api.yelp.com/v3/businesses/{ID}".format(ID=yelp_id)
    business_details_response = requests.get(business_id_url, headers=search_headers)
    # print(business_details_response.text)

    details_df = pd.DataFrame.from_dict([business_details_response.json()])

    # TODO: Explain how these fields can indicate great confidence that profile has been updated recently?
    # details_dict = {'id': business_details_response.json()['id'],
    #                 'name': business_details_response.json()['name'],
    #                 'alias': business_details_response.json()['alias'],
    #                 'is_claimed': business_details_response.json()['is_claimed'],
    #                 'review_count': business_details_response.json()['review_count'],
    #                 'categories': business_details_response.json()['categories'],
    #                 'is_closed': business_details_response.json()['is_closed'],
    #                 'zip_code': business_details_response.json()['location']['zip_code'],
    #                 'transactions:': business_details_response.json()['transactions']
    #                 }

    return details_df


def aggregate_details_from_search(search_results_df):
    details_list_to_agg = []
    yelp_id_list = search_results_df['id'].tolist()
    for yelp_id in yelp_id_list:
        details_list_to_agg.append(business_details_yelp(yelp_id))

    all_search_details_df = pd.concat(details_list_to_agg, sort=False)
    # TODO: Re-index?

    return all_search_details_df


def extract_zip_code(details_df_row):
    print('--------------------------------------------------------')
    print(details_df_row['location'])
    print(type(details_df_row['location']))
    print(details_df_row['location']['zip_code'])
    print(type(details_df_row['location']['zip_code']))
    if details_df_row['location']:
        if not isinstance(details_df_row['location']['zip_code'], str):
            return str(details_df_row['location']['zip_code'])
        elif len(details_df_row['location']['zip_code']) < 1:
            return None
        else:
            return details_df_row['location']['zip_code']
    else:
        print('NO ZIP CODE: ', details_df_row['id'], details_df_row['location'])
        return 'No zip code found'


def run_full_search(search_params):
    print("Searching for results matching '{}'...".format(search_params['location']))
    search_df = loop_offset_search(search_params)
    print('\nGetting details on all matching businesses (may take a few minutes)...')
    details_df = aggregate_details_from_search(search_df)
    details_df['location_search'] = search_params['location']
    # print(details_df.columns)
    # print(details_df.head())
    # print(details_df[['name', 'id', 'location', 'is_closed', 'is_claimed', 'transactions']])
    details_df['zip_code'] = details_df.apply(lambda row: extract_zip_code(row), axis=1)
    details_df['api_call_datetime'] = datetime.now()
    # print(details_df[['id', 'name', 'zip_code']])

    return details_df


# TODO: Get lat/long search params to work (why isn't it??)
#  Getting error: "{"error": {"code": "VALIDATION_ERROR", "description": "Please specify a location or a latitude and longitude"}}"
lat = float(33.769327)
long = float(-116.312849)
rad = int(4000)
params_lat_long = {
    'latitude:': lat,
    'longitude': long,
    'radius': rad
}



palm_springs_params = {
    'location': 'palm springs, CA',
    'limit': 50
}
# TODO: Searching by 'location' parameter can return erroneous results
#  (businesses in other similar-sounding cities, etc) -- validate results by zipcode obtained from location in details?

# palm_springs_df = run_full_search(palm_springs_params)
# palm_springs_df.to_pickle("./palm_springs.pkl")
palm_springs_df = pd.read_pickle("./palm_springs.pkl")
print(palm_springs_df.shape)
print(palm_springs_df.columns)
print(palm_springs_df)

print(palm_springs_df.groupby(by=['is_closed', 'is_claimed'], as_index=False)['id'].agg('count'))


indio_params = {
    'location': 'indio, CA',
    'limit': 50
}
indio_df = run_full_search(indio_params)
indio_df.to_pickle("./indio.pkl")

riverside_params = {
    'location': 'riverside, CA',
    'limit': 50
}
riverside_df = run_full_search(riverside_params)
riverside_df.to_pickle("./riverside.pkl")


sample_df = pd.concat([palm_springs_df, indio_df, riverside_df])
print(sample_df)



# TODO: Sample and collect a few cities/locations, aggregate into database (where? USDR/RTCovid resource?)

# TODO: Cross-reference businesses with FB, Google, etc? (by name, location?) Yelp business match: https://www.yelp.com/developers/documentation/v3/business_match
# TODO: Business closure rate, modified hours rate // segment by zip_code, biz category
# TODO: Identify Opportunity Zones (by zip_code)

# TODO: Hypothesis: economic activity in OZs is statistically significantly lower than that in non-OZs? Or is this too much further than 'just the facts'?

