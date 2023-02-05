import socket
import pickle
import cv2
import threading
import time
import uuid
import os
import datetime
import hashlib
import numpy as np
import json

from flask import Flask, request

from easyocr import Reader
from dotenv import dotenv_values

config = dotenv_values(".env")

current_GMT = time.gmtime()
time_stamp = calendar.timegm(current_GMT)

r = requests.post("http://localhost:" + config['PORT_API'] + "/course", data={"nom": config['NOM_COURSE'], 'timestamp': time_stamp}) 
id_course = json.loads(r.text)['id']
path_api = json.loads(r.text)['path']

HEADERSIZE = 15
ITER_NUMBER = 2
LAST_TIME = 10


def remove_image(name):
    os.remove(f'/tmp/{name}.png')


def get_image(name):
    image = cv2.imread(f'/tmp/{name}.png')
    creation_date = int(os.path.getctime(f'/tmp/{name}.png'))
    remove_image(name)
    return image, creation_date


def thread_function():
    time.sleep(1)
    while not fin or len(images_list):
        lock.acquire()
        if images_list:
            print('proccessing')
            name = images_list.pop(0)
            image, creation_date = get_image(name)
            lock.release()
            # image_process(image, creation_date, name)
            ratio = 1 # image.shape[1] # / 1000

            print(f"{name} | {images_info[name]}")
            people_positions = images_info[name]['people_positions']

            # Cropped image
            # for [xA, yA, xB, yB] in people_positions:
            for people in people_positions:
                (xA, yA, xB, yB) = (int(int(people[0])*ratio), int(int(people[1])*ratio), int(int(people[2])*ratio), int(int(people[3])*ratio))
                cropped_image = image[yA:yB, xA:xB]
                
                # ''', canvas_size=min(720,image.shape[1])'''
                results = reader.readtext(cropped_image, text_threshold=0.3, link_threshold=0.3, low_text=0.3)

                for (bbox, text, prob) in results:
                    text = cleanup_text(text)

                    if text.isdigit():
                        lock.acquire()
                        # bib_process(text, image, creation_date)
                        if not text in past_bibs:
                            # Create bib
                            if text not in bibs_dict:
                                bibs_dict[text] = {
                                    'iter_number': 1,
                                    'last_time': 0,
                                    'image': image
                                }

                            # Update bib data
                            bibs_dict[text]['iter_number'] += 1
                            bibs_dict[text]['last_time'] = 0

                            # Send image
                            if bibs_dict[text]['iter_number'] >= ITER_NUMBER:
                                with open('classement.txt', 'a') as f:
                                    f.write(f'Send picture {text} | creation date {datetime.datetime.fromtimestamp(creation_date)}\n')

                                # Save image (temporary)
                                unique_name = uuid.uuid4().hex

                                # Création du dossier du dossard s'il n'existe pas
                                if not os.path.exists(f'{path_api}/{id_course}/{text}'):
                                    os.makedirs(f'{path_api}/{id_course}/{text}')

                                # Requête à l'API pour enregistrer le passage du coureur
                                requests.post("http://localhost:" + config['PORT_API'] + "/pointControle", data={"dossard": text, "timestamp": creation_date, "distance": 5, "courseId": id_course}) 

                                # Enregistrement dans le dossier du dossard
                                cv2.imwrite(f'{path_api}/{id_course}/{text}/{unique_name}.png', bibs_dict[text]['image'])

                                # Update data
                                past_bibs.append(text)
                                bibs_dict.pop(text)

                        # Supp bib
                        bibs_keys = list(bibs_dict.keys())
                        for key in bibs_keys:
                            if key != text:
                                bibs_dict[key]['last_time'] += 1
                                if bibs_dict[key]['last_time'] >= LAST_TIME:
                                    bibs_dict.pop(key)
                        lock.release()
            continue
        lock.release()


def cleanup_text(text):
	return "".join([c if ord(c) < 128 else "" for c in text]).strip()


def bib_process(bib_number, image, creation_date):
    # Not pass
    if not bib_number in past_bibs:
        # Create bib
        if bib_number not in bibs_dict:
            bibs_dict[bib_number] = {
                'iter_number': 1,
                'last_time': 0,
                'image': image
            }

        # Update bib data
        bibs_dict[bib_number]['iter_number'] += 1
        bibs_dict[bib_number]['last_time'] = 0

        # Send image
        if bibs_dict[bib_number]['iter_number'] >= ITER_NUMBER:
            print(f'Send picture {bib_number} | creation date {datetime.datetime.fromtimestamp(creation_date)}')

            # Save image (temporary)
            unique_name = uuid.uuid4().hex
            cv2.imwrite(f'/tmp/{unique_name}.png', bibs_dict[bib_number]['image'])

            # Update data
            past_bibs.append(bib_number)
            bibs_dict.pop(bib_number)

    # Supp bib
    bibs_keys = list(bibs_dict.keys())
    for key in bibs_keys:
        if key != bib_number:
            bibs_dict[key]['last_time'] += 1
            if bibs_dict[key]['last_time'] >= LAST_TIME:
                bibs_dict.pop(key)


def image_process(orig_image, creation_date, name):
    print('proccessing')
    # Calculate ratio
    ratio = orig_image.shape[1] / 400

    people_positions = images_info[name]['informations']['people_position']

    # Cropped image
    for (xA, yA, xB, yB) in people_positions:
        (xA, yA, xB, yB) = (int(xA*ratio), int(yA*ratio), int(xB*ratio), int(yB*ratio))
        cropped_image = orig_image[yA:yB, xA:xB]
        
        results = reader.readtext(cropped_image, canvas_size=400, text_threshold=0.3, link_threshold=0.3, low_text=0.3)

        for (bbox, text, prob) in results:
            text = cleanup_text(text)

            if text.isdigit():
                lock.acquire()
                bib_process(text, orig_image, creation_date)
                lock.release()


images_list = []
bibs_dict = {}
past_bibs = []
images_info = {}
number_of_image = 0
fin = False

# Init thread
lock = threading.RLock()
thread = threading.Thread(target=thread_function)
thread.start()

# Init reader
reader = Reader(["fr"])

# API
app = Flask(__name__)


@app.route('/upload', methods=["POST"])
def upload():
    people_positions = request.form.get('people_positions')
    image = request.files.get('image')

    image = np.frombuffer(image.read(), dtype=np.uint8)
    image = cv2.imdecode(image, cv2.IMREAD_UNCHANGED)

    lock.acquire()
    unique_name = uuid.uuid4().hex
    cv2.imwrite(f'/tmp/{unique_name}.png', image)
    images_list.append(unique_name)
    images_info[unique_name] = {
        'people_positions': json.loads(people_positions)
    }
    lock.release()

    return "Image uploaded successfully"


if __name__ == "__main__":
    app.run(host="0.0.0.0")
