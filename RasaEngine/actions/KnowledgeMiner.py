#!/usr/bin/python

import neo4j
from neo4j import GraphDatabase
import re, string
import sys, getopt

"""
This CL tool is for processing text corpora by splitting
them into sequences of words and storing them into
a graph database.
"""


# default uri for local Neo4j instance
db_user = "neo4j"
db_pass = "12345"

graphdb = GraphDatabase.driver("bolt://localhost:7687", auth=(db_user, db_pass))

# parameterized Cypher query for data insertion
# t is a query parameter. a list with two elements: [word1, word2]
INSERT_QUERY_SIMPLE = '''
    FOREACH (t IN $wordPairs |
        MERGE (w0:Word {word: t[0]})
        MERGE (w1:Word {word: t[1]})
        CREATE (w0)-[:NEXT_WORD]->(w1)
        )
'''

INSERT_QUERY = '''
    FOREACH (t IN $wordPairs | 
        MERGE (w0:Word {word: t[0]})
            ON CREATE SET w0.count = 1
            ON MATCH SET w0.count = w0.count + 1
        MERGE (w1:Word {word: t[1]})
            ON CREATE SET w1.count = 1
            ON MATCH SET w1.count = w1.count + 1
        MERGE (w0)-[r:NEXT_WORD]->(w1)
            ON CREATE SET r.count = 1
            ON MATCH SET r.count = r.count + 1
        )
'''


# convert a sentence string into a list of lists of adjacent word pairs
# also convert to lowercase and remove punctuation using a regular expression
# arrifySentence("Hi there, Bob!) = [["hi", "there"], ["there", "bob"]]
def arrifySentence(sentence):
    sentence = sentence.lower()
    sentence = sentence.strip()
    exclude = set(string.punctuation)
    regex = re.compile('[%s]' % re.escape(string.punctuation))
    sentence = regex.sub('', sentence)
    wordArray = sentence.split()
    tupleList = []
    for i, word in enumerate(wordArray):
        if i+1 == len(wordArray):
            break
        tupleList.append([word, wordArray[i+1]])
    return tupleList

# load our text corpus into Neo4j
def loadFile(file_name):
    with graphdb.session(default_access_mode=neo4j.WRITE_ACCESS) as session:
        with open(file_name, encoding='UTF-8') as f:
            tx = session.begin_transaction()
            count = 0
            for l in f:
                params = {'wordPairs': arrifySentence(l)}
                tx.run(INSERT_QUERY, params)
                count += 1
                # process in batches of 100 insertion queries
                if count > 100:
                    tx.commit()
                    tx = session.begin_transaction()
                    count = 0
        f.close()
        tx.commit()
        session.close()



# get the set of words that appear to the left of a specified word in the text corpus
LEFT1_QUERY = '''
    MATCH (s:Word {word: $word})
    MATCH (w:Word)-[:NEXT_WORD]->(s)
    RETURN w.word as word
'''

# get the set of words that appear to the right of a specified word in the text corpus
RIGHT1_QUERY = '''
    MATCH (s:Word {word: $word})
    MATCH (w:Word)<-[:NEXT_WORD]-(s)
    RETURN w.word as word
'''

# return a set of all words that appear to the left of `word`
def left1(word):
    params = {
        'word': word.lower()
    }
    with graphdb.session(default_access_mode=neo4j.READ_ACCESS) as session:
        tx = session.begin_transaction()
        results = tx.run(LEFT1_QUERY, params)
        #results = tx.commit()
        words = []
        for result in results:
            for line in result:
                words.append(line)
        return set(words)

# return a set of all words that appear to the right of `word`
def right1(word):
    params = {
        'word': word.lower()
    }
    with graphdb.session(default_access_mode=neo4j.READ_ACCESS) as session:
        tx = session.begin_transaction()
        results = tx.run(RIGHT1_QUERY, params)
        #results = tx.commit()
        words = []
        for result in results:
            for line in result:
                words.append(line)
        return set(words)

# compute Jaccard coefficient
def jaccard(a,b):
    intSize = len(a.intersection(b))
    unionSize = len(a.union(b))
    return intSize / unionSize

# we define paradigmatic similarity as the average of the Jaccard coefficents of the `left1` and `right1` sets
def paradigSimilarity(w1, w2):
    return (jaccard(left1(w1), left1(w2)) + jaccard(right1(w1), right1(w2))) / 2.0



def analyzeMode():
    print(paradigSimilarity("uni", "studium"))


# Left/right word filter with jaccard similarity update
PARADIGM_QUERY='''
MATCH (s:Word)
// Get right1, left1
MATCH (w:Word)-[:NEXT_WORD]->(s)
WITH collect(DISTINCT w.word) as left1, s
MATCH (w:Word)<-[:NEXT_WORD]-(s)
WITH left1, s, collect(DISTINCT w.word) as right1
// Match every other word
MATCH (o:Word) WHERE NOT s = o
WITH left1, right1, s, o
// Get other right, other left1
MATCH (w:Word)-[:NEXT_WORD]->(o)
WITH collect(DISTINCT w.word) as left1_o, s, o, right1, left1
MATCH (w:Word)<-[:NEXT_WORD]-(o)
WITH left1_o, s, o, right1, left1, collect(DISTINCT w.word) as right1_o
// compute right1 union, intersect
WITH [x IN right1 WHERE x IN right1_o] as r1_intersect,
  (right1 + right1_o) AS r1_union, s, o, right1, left1, right1_o, left1_o
// compute left1 union, intersect
WITH [x IN left1 WHERE x IN left1_o] as l1_intersect,
  (left1 + left1_o) AS l1_union, r1_intersect, r1_union, s, o
WITH DISTINCT r1_union as r1_union, l1_union as l1_union, r1_intersect, l1_intersect, s, o
WITH 1.0*size(r1_intersect) / size(r1_union) as r1_jaccard,
  1.0*size(l1_intersect) / size(l1_union) as l1_jaccard,
  s, o
WITH s, o, r1_jaccard, l1_jaccard, r1_jaccard + l1_jaccard as sim
WHERE sim > 0
MERGE (s)-[r:RELATED_TO]->(o) SET r.paradig = sim;
'''

# With limit (because of too  much data):
PARADIGM_QUERY_LIMIT='''
MATCH (s:Word)
// Get right1, left1
MATCH (w:Word)-[:NEXT_WORD]->(s)
WITH collect(DISTINCT w.word) as left1, s LIMIT 100
MATCH (w:Word)<-[:NEXT_WORD]-(s)
WITH left1, s, collect(DISTINCT w.word) as right1
// Match every other word LIMIT 100
MATCH (o:Word) WHERE NOT s = o
WITH left1, right1, s, o
// Get other right, other left1 LIMIT 100
MATCH (w:Word)-[:NEXT_WORD]->(o)
WITH collect(DISTINCT w.word) as left1_o, s, o, right1, left1 LIMIT 100
MATCH (w:Word)<-[:NEXT_WORD]-(o)
WITH left1_o, s, o, right1, left1, collect(DISTINCT w.word) as right1_o LIMIT 100
// compute right1 union, intersect
WITH [x IN right1 WHERE x IN right1_o] as r1_intersect,
  (right1 + right1_o) AS r1_union, s, o, right1, left1, right1_o, left1_o 
// compute left1 union, intersect
WITH [x IN left1 WHERE x IN left1_o] as l1_intersect,
  (left1 + left1_o) AS l1_union, r1_intersect, r1_union, s, o
WITH DISTINCT r1_union as r1_union, l1_union as l1_union, r1_intersect, l1_intersect, s, o
WITH 1.0*size(r1_intersect) / size(r1_union) as r1_jaccard,
  1.0*size(l1_intersect) / size(l1_union) as l1_jaccard,
  s, o
WITH s, o, r1_jaccard, l1_jaccard, r1_jaccard + l1_jaccard as sim LIMIT 100
MERGE (s)-[r:RELATED_TO]->(o) SET r.paradig = sim;
'''


# return a set of all words that appear to the left of `word`
def paradigm_query():
    with graphdb.session(default_access_mode=neo4j.WRITE_ACCESS) as session:
        tx = session.begin_transaction()
        tx.run(PARADIGM_QUERY)
        tx.commit()
        tx.close()
        session.close()


def main(argv):
   inputfile = ''
   mode = ''
   try:
      opts, args = getopt.getopt(argv,"hm:i:",["mode=", "ifile="])
   except getopt.GetoptError:
      print('KnowledgeMiner.py -m <mode> -i <inputfile>')
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print('KnowledgeMiner.py -m <mode> -i <inputfile>')
         sys.exit()
      elif opt in ("-i", "--ifile"):
         inputfile = arg
      elif opt in ("-m", "--mode"):
         mode = arg
   print('Input file is "', inputfile)
   print('Mode is "', mode)

if __name__ == "__main__":
   main(sys.argv[1:])