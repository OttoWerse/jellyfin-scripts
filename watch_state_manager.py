import io, os, re
import sys
import json
from jellyfin_apiclient_python import JellyfinClient

server_url = os.getenv('ZAHHAK_MYSQL_HOSTNAME')
username = os.getenv('JELLYFIN_USERNAME')
password = os.getenv('JELLYFIN_PASSWORD')
if server_url is None or username is None or password is None:
    print('ERROR getting environmental variables')
    sys.exit()

'''DEBUG Settings'''
DEBUG_print_video_object = False
DEBUG_print_item_object = False
DEBUG_print_tmp_path = False
DEBUG_print_video_entry = False

'''!DO NOT TOUCH THESE!'''
limit = 1000000  # TODO: Set this dynamically to lib size or to int max?
http_timeout = 180  # TODO: IDK if this can be higher than 120, sometimes it seems to be not enough already

# TODO: This should be done using ArgParse!
mode_selected = False
while not mode_selected:
    mode_input = input(f'What do you want to do? '
                       f'(E)xport or '
                       f'(I)mport: ')
    if mode_input.lower() == 'e':
        mode_selected = True
        IMPORT = False
        EXPORT = True
    elif mode_input.lower() == 'i':
        mode_selected = True
        IMPORT = True
        EXPORT = False
    else:
        continue

'''INIT'''
if IMPORT:
    watched_videos = []
    with open('IMPORT.txt') as file:
        for line in file:
            watched_videos.append(line.rstrip())
if EXPORT:
    export_string = ''


'''MAIN'''
print(f'CONNECTING to JellyFin...')
client = JellyfinClient()
client.config.app('youtube_watch_extractor', '0.0.1', 'machine_name', 'unique_id')  # TODO: Unique ID and machine name!
client.config.data['auth.ssl'] = True
client.config.data['http.timeout'] = http_timeout
client.auth.connect_to_address(server_url)
client.auth.login(server_url, username,
                  password)  # TODO: The username here should be always Administrator AFAIK, it is for Server access, not user data stuff like watch history etc.
credentials = client.auth.credentials.get_credentials()
server = credentials['Servers'][0]
server['username'] = username  # TODO: This is the username for watch state etc.
json.dumps(server)
videos = client.jellyfin.search_media_items(media='Videos', limit=limit)['Items']
video_count = len(videos)
print(f'FOUND {video_count} videos to process')
for video in videos:
    if DEBUG_print_video_object:
        input(f'VIDEO: {video}')
    try:
        video_id = video['Id']
        # media = client.jellyfin.get_media_segments(item_id = video_id)
        # input(media)
        # parts = client.jellyfin.get_additional_parts(item_id = video_id)
        # input(parts)
        items = client.jellyfin.get_items(item_ids=[video_id, ])['Items']
        for item in items:
            if DEBUG_print_item_object:
                input(f'ITEM: {item}')
            item_type = item['MediaType']
            if item_type != 'Video':
                continue  # Skip TV-Show and Seasons objects
            id_found = False
            try:
                item_path = item['Path']
                try:
                    item_ids = item['ProviderIds']
                    for item_id in item_ids:
                        video_site = item_id
                        video_url = item_ids.get(item_id)
                        video_entry = f'{video_site} {video_url}'
                        if DEBUG_print_video_entry:
                            input(f'{video_entry}')
                        id_found = True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_item_ids:
                    print(f'EXCEPTION getting item IDs: {exception_item_ids}')
                if not id_found:
                    json_path = re.sub(r'\.mp4$', '.info.json', item_path)
                    print(f'LOADING JSON "{json_path}"')
                    if os.path.exists(json_path):
                        with io.open(json_path, 'r', encoding='utf-8-sig') as json_txt:
                            try:
                                json_obj = json.load(json_txt)
                                try:
                                    video_url = json_obj['id']
                                    video_site = json_obj['extractor']
                                    video_entry = f'{video_site} {video_url}'
                                    if DEBUG_print_video_entry:
                                        input(f'{video_entry}')
                                    id_found = True
                                except KeyboardInterrupt:
                                    sys.exit()
                                except Exception as exception_json_field:
                                    print(exception_json_field)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_json_read:
                                print(exception_json_read)
                if not id_found:
                    with io.open('MISSING_JSON.txt', 'a') as missing_json_file:
                        missing_json_file.write(f'{item_path}\n')
                        print(f'NO ID ({item_path})')
                    continue
                if EXPORT:
                    userdata = client.jellyfin.get_userdata_for_item(item_id=video_id)
                    watched = userdata['Played']
                    if watched:
                        print(f'EXPORTING "{video_entry}" ({item_path})')
                        export_string += f'{video_entry}\n'
                if IMPORT:
                    if video_entry in watched_videos:
                        print(f'IMPORTING "{video_entry}" ({item_path})')
                        client.jellyfin.item_played(item_id=video_id, watched=True)  # TODO: date from Emby to Jellyfin?
            except KeyboardInterrupt:
                sys.exit()
            except Exception as e:
                print(e)
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(e)

if EXPORT:
    print(f'SAVING EXPORT...')
    with open('EXPORT.txt', 'w') as file:
        file.write(export_string)
