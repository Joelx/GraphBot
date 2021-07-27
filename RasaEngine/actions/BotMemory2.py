

"""
  A wrapper class to interface with neo4j graph database.
  The interface is acting as "memory".
"""

#from neo4jrestclient.client import GraphDatabase
from neo4jrestclient import client
from neo4j import GraphDatabase
from random import randrange


class BotMemory:
    """
        Wrapper class for neo4j db.
        allows to read and extend bot memory.
    """
    def __init__(self, db_user, db_pass, host="bolt://localhost:7687"):
        # connect to the database.
        self.db = GraphDatabase.driver(host, auth=(db_user, db_pass))
        print("connected")

    @classmethod
    def _create_person_query(cls, tx, name):
        tx.run("MERGE (:Person {name: $name})", name=name)

    def create_person(self, name):
        with self.db.session() as session_create_person:
            session_create_person.write_transaction(self._create_person_query, name)

    # V2.0
    # Create an gender property to a pre-existing person node.
    # This relies on the person first having been created.
    # Src: https://neo4j.com/docs/driver-manual/1.7/sessions-transactions/#driver-transactions-transaction-functions
    @classmethod
    def _add_gender_query(cls, tx, person_name, gender):
        # Get GenderIDs via dictionary. For prototyping only.
        genderIDs = {"männlich": 0, "weiblich": 1, "divers": 2}
        # Add properties for gender and genderID
        tx.run("MATCH (p:Person {name: $person_name}) "
               "MATCH (g:Geschlecht {name: $gender}) "
               "SET p.gender = $gender, p.genderID = $genderID "
               "CREATE (p)-[:HAS_GENDER]->(g)",
               person_name=person_name, gender=gender, genderID=genderIDs[gender])
    def add_gender(self, person_name, gender):
        with self.db.session() as session_add_gender:
            session_add_gender.write_transaction(self._add_gender_query, person_name, gender)

    @classmethod
    def _add_age_query(cls, tx, person_name, age):
        tx.run("MATCH (p:Person {name: $person_name}) SET p.age = $age",
               person_name=person_name, age=age)
    def add_age(self, person_name, age):
        with self.db.session() as session_add_age:
            session_add_age.write_transaction(self._add_age_query, person_name, age)

    @classmethod
    def _get_person_from_name_query(cls, tx, name):
        result = tx.run("MATCH (n) WHERE n.name = $name RETURN n.name as name, n.gender as gender, n.age as age", name=name)
        ret=[]
        for record in result:
            ret.append({"name": record["name"], "gender": record["gender"], "age": record["age"]})
        return ret

    def get_person_from_name(self, name):
        with self.db.session() as session_get_node:
            result = session_get_node.read_transaction(self._get_node_from_name_query, name)
            return result



    def get_user(self, _user_name):
        session = self.db.session()
        q = "MATCH (n:Person) WHERE n.name = '" + _user_name + "' RETURN n.name AS name, n.gender AS gender, n.age as age"
        res = session.run(q)
        user = {}
        for record in res:
            user = {
                "name": record["name"],
                "gender": record["gender"],
                "age": record["age"]
            }
        if not dict(user):
            user = False
        session.close()
        return user

    def run_query(self, query_string):
        session = self.db.session()
        res = session.run(query_string)
        session.close()
        return res

    def get_user_favorite_class(self, u):
        favorite_class = None
        session = self.db.session()
        q = 'MATCH p=(u:user_name {name:"' + u + '"})-[:likes]->(ul:favorite_class) RETURN ul'
        results = self.db.query(q, data_contents=True)
        session.close()
        if len(results) > 0:
            favorite_class = results.rows[0][0]["name"]
        return favorite_class

    def normalize_properties(self, _node_label, _property_name):
        session = self.db.session()
        q = "MATCH (n:" + _node_label + ") WITH max(toInteger(n." + _property_name + ")) AS max," \
            "min(toInteger(n." + _property_name + ")) AS min " \
            "MATCH (n1:" + _node_label + ") SET n1." + _property_name + "Norm = (1.0 * toInteger(n1." + \
            _property_name + ") - min) / (max - min)"
        res = session.run(q)
        session.close()
        return res

    def create_cosine_similarity(self, _node_label, _property_name, _list_features):
        session = self.db.session()
        object_string_p1 = ",".join(["toFloat(p1." + s + ")" for s in _list_features])
        object_string_p2 = ",".join(["toFloat(p2." + s + ")" for s in _list_features])
        q = "MATCH (p1:" + _node_label + "),(p2:" + _node_label + ") " \
            "WHERE id(p1) < id(p2) AND exists(p1." + _property_name + ") AND exists(p2." + _property_name + ") " \
            "WITH p1,p2,gds.alpha.similarity.cosine([" + object_string_p1 + "],[" + object_string_p2 + "]) AS value " \
            "MERGE (p1)-[s:SIMILARITY]-(p2) " \
            "SET s.cosine = value"
        res = session.run(q)
        session.close()
        return res

    def get_contraception_recommendations(self, _property_name, _property_value):
        session = self.db.session()
        q = "MATCH (p1:Person {" + _property_name + ":'" + _property_value + "'})-[r1:SIMILARITY]-(p2:Person) " \
            "MATCH (p2)-[r2:CONTRACEPTS_WITH]->(c:Verhütung) " \
            "WHERE r1.cosine > 0.8 " \
            "RETURN p2.name as personName, r1.cosine as similarity, c.name as contraceptionName " \
            "ORDER BY r1.cosine DESC"
        res = session.run(q)
        recommendations = []
        for record in res:
            recommendations.append({
                "contraception": record["contraceptionName"],
                "similarity": record["similarity"],
            })
        if not list(recommendations):
            recommendations = False
        session.close()

        return recommendations

    def get_contraception(self, _name):
        session = self.db.session()
        q = "MATCH (n:Verhütung) WHERE " \
            "n.name = '" + _name +"' Return n.name as name, n.description as description, " \
            "n.advantages as advantages, n.disadvantages as disadvantages "
        res = session.run(q)
        contraceptions = []
        for record in res:
            contraceptions.append({
                "name": record["name"],
                "description": record["description"],
                "advantages": record["advantages"],
                "disadvantages": record["disadvantages"]
            })
        if not list(contraceptions):
            contraceptions = False
        session.close()
        return contraceptions



def is_result_record(results):
    try:
        results.peek()
    except Exception:
        return False
    else:
        return results
