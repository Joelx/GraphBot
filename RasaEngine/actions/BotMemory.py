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
        Simple wrapper class.
        allows to add to memory.
        perform simple inference.
    """
    def __init__(self, db_user, db_pass, host="bolt://localhost:7687"):
        # connect to the database.
        #self.db = GraphDatabase(host, username=db_user, password=db_pass)
        self.db = GraphDatabase.driver(host, auth=(db_user, db_pass))
        print("connected")


    def memorize_user_facts(self, name, age=None, gender=None, favorite_class=None, favorite_movie=None, mood=None):
        """
           A method to memorize facts about user.
        """
        n = self.add_node(name, "Person")
        if age is not None:
            #a = self._add_node(age, "age")
            ra = self.add_property(name, "age", age)
        if gender is not None:
            g = self.add_node(gender, "Gender")
            rg = self.add_property(name, "gender", gender)
        if favorite_class is not None:
            fc = self.add_node(favorite_class, "Class")
            rfc = self.add_relationship(name, favorite_class, "Person", "Class", "interested_in")
        if favorite_movie is not None:
            fm = self.add_node(favorite_movie, "Movie")
            fmr = self.add_relationship(name, favorite_movie, "Person", "Movie", "likes")
        if mood is not None:
            m = self.add_node(mood, "Mood")
            mr = self.add_relationship(name, mood, "Person", "Mood", "feels")

    # def clear_memory(self):
    #     """
    #        forget everything.
    #     """
    #     q = "MATCH (n:user_name) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))
    #     q = "MATCH (n:age) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))
    #     q = "MATCH (n:gender) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))
    #     q = "MATCH (n:favorite_class) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))
    #     q = "MATCH (n:favorite_movie) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))
    #     q = "MATCH (n:mood) DETACH DELETE n"
    #     results = self.db.query(q, returns=(client.Node, str, client.Node))

    def add_node(self, _node_name, _node_label):
        """
            add a node if not existed.
            and return the node.
        """
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = 'MERGE (p:' + _node_label + ' {name: "' + _node_name + '"}) RETURN p'
        res = session.run(q)
        session.close()

        return res

    def add_relationship(self, _node_name_a, _node_name_b, _node_type_a, _node_type_b, _relationship):
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = """
        MATCH (p:{node_type_a}), (m:{node_type_b}) 
        WHERE p.name='{node_name_a}' 
        AND m.name='{node_name_b}' 
        MERGE (p)-[r:{relationship}]->(m) 
        RETURN r
        """
        q = q.format(node_type_a=_node_type_a, node_type_b=_node_type_b,
                     node_name_a=_node_name_a, node_name_b=_node_name_b,
                     relationship=_relationship)
        res = session.run(q)
        session.close()
        return res

    def add_property(self, _node_name, _property_name, _property_value):
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = "MATCH (p {name: '" + _node_name + "'}) SET p." + _property_name + " = '" + _property_value +"' RETURN p"
        res = session.run(q)
        session.close()
        if _property_name is "gender":
            # First, get corresponding genderID
            res = self.get_node_with_property("Geschlecht", "name", _property_value)
            genderID = res[0].get("n")._properties["genderID"]
            self.add_relationship(_node_name, _property_value, "Person", "Geschlecht", "HAS_GENDER")
            self.add_property(_node_name, "genderID", genderID)

        return res

    def get_node_with_property(self, _node_label, _property_name, _property_value):
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = "MATCH (n:" + _node_label + ") WHERE n." + _property_name + " = '" + _property_value + "' RETURN n"
        res = session.run(q)
        if not list(res):
            res = False
        session.close()
        return res

    def get_user(self, _user_name):
        session = self.db.session()  # For every route a seperate session! Close it after route!
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
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = 'MATCH p=(u:user_name {name:"' + u + '"})-[:likes]->(ul:favorite_class) RETURN ul'
        results = self.db.query(q, data_contents=True)
        session.close()
        if len(results) > 0:
            favorite_class = results.rows[0][0]["name"]
        return favorite_class

    def normalize_properties(self, _node_label, _property_name):
        session = self.db.session()  # For every route a seperate session! Close it after route!
        q = "MATCH (n:" + _node_label + ") WITH max(toInteger(n." + _property_name + ")) AS max," \
            "min(toInteger(n." + _property_name + ")) AS min " \
            "MATCH (n1:" + _node_label + ") SET n1." + _property_name + "Norm = (1.0 * toInteger(n1." + \
            _property_name + ") - min) / (max - min)"
        res = session.run(q)
        session.close()
        return res

    #TODO: Möglicherweise parameter "normalize = false/true" oder so.. aber noch nicht sicher, ob sinnvoll
    #TODO: evtl _property_name herausnehmen...
    def create_cosine_similarity(self, _node_label, _property_name, _list_features):
        session = self.db.session()
        object_string_p1 = ",".join(["toFloat(p1." + s + ")" for s in _list_features])
        object_string_p2 = ",".join(["toFloat(p2." + s + ")" for s in _list_features])
        q = "MATCH (p1:" + _node_label + "),(p2:" + _node_label + ") " \
            "WHERE id(p1) < id(p2) AND exists(p1." + _property_name + ") AND exists(p2." + _property_name + ") " \
            "WITH p1,p2,gds.alpha.similarity.cosine([" + object_string_p1 + "],[" + object_string_p2 + "]) AS value " \
            "MERGE (p1)-[s:SIMILARITY]-(p2) " \
            "SET s.cosine = value"
        #return q
        res = session.run(q)
        session.close()
        return res

    # Dummy funktion für verhütung. noch nicht generalisiert.
    def get_contraception_recommendations(self, _property_name, _property_value):
        session = self.db.session()
        q = "MATCH (p1:Person {" + _property_name + ":'" + _property_value + "'})-[r1:SIMILARITY]-(p2:Person) " \
            "MATCH (p2)-[r2:CONTRACEPTS_WITH]->(c:Verhütung) " \
            "WHERE r1.cosine > 0.8 " \
            "RETURN p2.name as personName, r1.cosine as similarity, c.name as contraceptionName " \
            "ORDER BY r1.cosine DESC"
        #return q
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

    def memorize_restaurant_facts(self, name, cuisine=None, location=None):
        """
           A method to memorize facts related to restaurants
        """
        n = self.add_node(name, "restaurant_name")
        if cuisine is not None:
            c = self.add_node(cuisine, "cuisine")
            n.relationships.create("is_a", c)
        if location is not None:
            l = self.add_node(location, "location")
            n.relationships.create("located", l)
    # def find_restaurant(self, u, c):
    #     """
    #        find a good choice!
    #        Should handle when there is no result or
    #        when user location is not specified.
    #        If cuisine c specified apply it.
    #     """
    #     r_name = None
    #     r_location = None
    #     r_cuisine = None
    #     u_name = u
    #
    #     if c is not None:
    #         q0 = 'MATCH p=(rl:location)<-[:located]-(res:restaurant_name)-[r:is_a]->(c:cuisine {name:"' + c + '"})<-[:likes]-(u:user_name {name:"' + u + '"})-[:located]->(ul:location) where ul=rl RETURN res, c, u, rl  LIMIT 25'
    #         results = self.db.query(q0, data_contents=True)
    #         if (len(results) > 0):
    #             random_index = randrange(0, len(results))
    #             r_name = results.rows[random_index][0]["name"]
    #             r_location = results.rows[random_index][3]["name"]
    #             r_cuisine = results.rows[random_index][1]["name"]
    #             return (u_name, r_name, r_location, r_cuisine)
    #
    #     q1 = 'MATCH p=(rl:location)<-[:located]-(res:restaurant_name)-[r:is_a]->(c:cuisine)<-[:likes]-(u:user_name {name:"' + u + '"})-[:located]->(ul:location) where ul=rl RETURN res, c, u, rl  LIMIT 25'
    #
    #     results = self.db.query(q1, data_contents=True)
    #     if (len(results) > 0):
    #         random_index = randrange(0, len(results))
    #         r_name = results.rows[random_index][0]["name"]
    #         r_location = results.rows[random_index][3]["name"]
    #         r_cuisine = results.rows[random_index][1]["name"]
    #         return (u_name, r_name, r_location, r_cuisine)
    #
    #     q2 = 'MATCH p=(u:user_name {name:"' + u + '"})-[:located]->(ul:location)<-[:located]-(res:restaurant_name)  RETURN res, u, ul  LIMIT 25'
    #     results = self.db.query(q2, data_contents=True)
    #     if (len(results) > 0):
    #         random_index = randrange(0, len(results))
    #         r_name = results.rows[random_index][0]["name"]
    #         r_location = results.rows[random_index][2]["name"]
    #
    #     return (u_name, r_name, r_location, r_cuisine)

#
# db_user = "neo4j"
# db_pass = "12345"
#
# bot_mem = BotMemory(db_user, db_pass)
#
# _name="Tim"
# _age="17"
# _gender="Junge"
# _favorite_class="Mathe"
# _favorite_movie="John Wick"
# _mood="prima"
#
# bot_mem.memorize_user_facts(_name, _age, _gender, _favorite_class, _favorite_movie, _mood)


def is_result_record(results):
    try:
        results.peek()
    except Exception:
        return False
    else:
        return results
