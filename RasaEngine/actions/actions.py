#import yaml
import pathlib
from typing import Text, List, Any, Dict, Optional

from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from . import BotMemory2 as bm

names = pathlib.Path("data/names.txt").read_text().split("\n")
genders_female = ['mädchen', 'mädel', 'weiblich', 'frau', 'weiblich']
genders_male = ['junge', 'kerl', 'mann', 'männlich']

#db_host = "bolt://localhost:7687"
db_user = "neo4j"
db_pass = "12345"

bot_mem = bm.BotMemory(db_user, db_pass)


class ValidateNameForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_name_form"

    async def required_slots(
            self,
            slots_mapped_in_domain: List[Text],
            dispatcher: "CollectingDispatcher",
            tracker: "Tracker",
            domain: "DomainDict",
    ) -> Optional[List[Text]]:
        first_name = tracker.slots.get("first_name")
        if first_name is not None:
            if first_name.lower() not in names:
                return ["name_spelled_correctly"] + slots_mapped_in_domain
        return slots_mapped_in_domain

    async def extract_name_spelled_correctly(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        intent = tracker.get_intent_of_latest_message()
        return {"name_spelled_correctly": intent == "affirm"}

    def validate_name_spelled_correctly(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate `first_name` value."""
        if tracker.get_slot("name_spelled_correctly"):
            return {"first_name": tracker.get_slot("first_name"), "name_spelled_correctly": True}
        return {"first_name": None, "name_spelled_correctly": None}

    def validate_first_name(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate `first_name` value."""

        # If the name is super short, it might be wrong.
        print(f"First name given = {slot_value} length = {len(slot_value)}")
        if len(slot_value) <= 1:
            dispatcher.utter_message(text=f"That's a very short name. I'm assuming you mis-spelled.")
            return {"first_name": None}
        # First check if user is already known!
        known_user = bot_mem.get_user(slot_value)
        if known_user:
            print("User known!")
            dispatcher.utter_message(f"Ah! Wir kennen uns schon, {slot_value}. Schön, dich wiederzusehen! :)")
            user_gender = known_user["gender"]
            user_age = known_user["age"]
            return {"first_name": slot_value, "gender": user_gender, "age": user_age, "user_known": True} # TODO: make a dedicated slot for known user and exit form properly!
        else:
            print("Creating record for user")
            bot_mem.create_person(slot_value) # Test purpose. Belongs into a submit!
            return {"first_name": slot_value}


    # def validate_last_name(
    #         self,
    #         slot_value: Any,
    #         dispatcher: CollectingDispatcher,
    #         tracker: Tracker,
    #         domain: DomainDict,
    # ) -> Dict[Text, Any]:
    #     """Validate `last_name` value."""
    #
    #     # If the name is super short, it might be wrong.
    #     print(f"Last name given = {slot_value} length = {len(slot_value)}")
    #     if len(slot_value) <= 1:
    #         dispatcher.utter_message(text=f"That's a very short name. I'm assuming you mis-spelled.")
    #         return {"last_name": None}
    #     else:
    #         return {"last_name": slot_value}


class ValidateContraceptionForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_contraception_form"

    async def required_slots(
            self,
            slots_mapped_in_domain: List[Text],
            dispatcher: "CollectingDispatcher",
            tracker: "Tracker",
            domain: "DomainDict",
    ) -> Optional[List[Text]]:
        return ["gender", "age"]



    def validate_gender(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        gender = ""
        tracker_gender = tracker.get_slot("gender")
        if tracker_gender:
            #dispatcher.utter_message("Du bist " + tracker.get_slot("gender"))
            print(tracker_gender)
            #return {"gender": slot_value}
        if tracker_gender.lower() in genders_female:
            gender = "weiblich"
        elif tracker_gender.lower() in genders_male:
            gender = "männlich"
        else:
            gender = "divers"
      #  dispatcher.utter_message("Validating gender..")
        name = tracker.get_slot("first_name")
        print("Setting user gender: " + gender)
        #bot_mem.add_property(name, "gender", gender)
        bot_mem.add_gender(name, gender)
        return {"gender": gender}

    def validate_age(
            self,
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict,
    ) -> Dict[Text, Any]:
        age = tracker.get_slot("age")
        if age:
            dispatcher.utter_message("Du bist " + tracker.get_slot('gender') + " und " + age + " Jahre alt.")
            #return {"age": slot_value}
        # TODO: Validiere alter.. z.b. zwischen 5 und 50 oder so
      #  dispatcher.utter_message("Validating age..")
        name = tracker.get_slot("first_name")
        #bot_mem.add_property(name, "age", slot_value)
        bot_mem.add_age(name, age)
        return {"age": age}


class ContraceptionInfo(Action):
    def name(self) -> Text:
        return "contraception_info"

    async def run(
        self, dispatcher, tracker: Tracker, domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        try:
            bot_mem.normalize_properties("Person", "age") # Re-Normalize age property in case there is new data
            bot_mem.create_cosine_similarity("Person", "age", ["genderID", "ageNorm"]) # Update cosine similarities
            results = bot_mem.get_contraception_recommendations("name", tracker.get_slot("first_name"))
            if not (list(results)):
                dispatcher.utter_message("Tut mir leid. Ich kann dir hier gerade nicht helfen :(")
                return []
            # Create dict with contraception as value and frequency as value
            #individualContraceptionCount = {i:results.count(i) for i in results}
            # Sort by frequency
            #dict(sorted(individualContraceptionCount.items(), key=lambda item: item[1]))
            if len(results) > 1:
                dispatcher.utter_message("Basierend auf deinem Alter und Geschlecht "
                                         "könnten die folgenden Verhütungsmethoden zu dir passen: ")
            else:
                dispatcher.utter_message("Basierend auf deinem Alter und Geschlecht "
                                         "könnte die folgenden Verhütungsmethode zu dir passen: ")
            # Remove duplicates .. TODO: use freuency of occurence
            seen = set()
            result = []
            for dic in results:
                key = (dic['contraception'])
                if key in seen:
                    continue
                result.append(dic)
                seen.add(key)

            from pprint import pprint
            pprint(result)
            for res in result:
                contraceptionName = str(res["contraception"])
                dispatcher.utter_message(contraceptionName)
                contraception = bot_mem.get_contraception(contraceptionName)
                if contraception:
                    dispatcher.utter_message("Folgendes kann ich dir dazu sagen:")
                    dispatcher.utter_message("Beschreibung: " + contraception[0]["description"])
                    dispatcher.utter_message("Vorteile: " + contraception[0]["advantages"])
                    dispatcher.utter_message("Nachteile: " + contraception[0]["disadvantages"])
                    dispatcher.utter_message("")
        except TypeError:
            dispatcher.utter_message("Tut mir leid. Ich kann dir hier gerade nicht helfen :(")
        return []