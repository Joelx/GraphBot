from bs4 import BeautifulSoup
import os

"""
Reads all XML files in declared directory 
and all it's subdirectories and stores
them into a single file.
"""

rootdir = 'Chat Korpus'

for subdir, dirs, files in os.walk(rootdir):
    for file in files:
        if file.endswith('.xml'):
            print(os.path.join(subdir, file))
            soup = BeautifulSoup(open(os.path.join(subdir, file),'r'), 'lxml')
            mesageBodies = [i.text.strip() for i in soup.select("message[type=utterance] > messageBody")]
            with open('chat-korpus.txt', 'a', encoding='utf-8') as f:
                for item in mesageBodies:
                    f.write("%s\n" % item)

