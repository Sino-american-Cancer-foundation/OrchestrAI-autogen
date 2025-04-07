from neo4j import GraphDatabase
from typing import List, Dict, Optional, Tuple
import re

class DecisionPoint:
    def __init__(self, id: str, question: str, condition_query: str,  
                 if_met: Optional['TherapyOption' or 'DecisionPoint' or 'Page'] = None, 
                 if_not_met: Optional['TherapyOption' or 'DecisionPoint' or 'Page'] = None):
        self.id = id
        # self.description = description
        self.question = question
        self.condition_query = condition_query
        self.if_met = if_met
        self.if_not_met = if_not_met

    def _to_json(self):
        return {
            "id": self.id,
            # "description": self.description,
            "question": self.question,
            "condition_query": self.condition_query,
            "if_met": str(self.if_met) if self.if_met else None,
            "if_not_met": str(self.if_not_met) if self.if_not_met else None
        }

    def evaluate(self, patient_data: List[Dict[str, str]], session) -> tuple[Optional['TherapyOption' or 'DecisionPoint' or 'Page'], List[Dict[str, str]]]:
        missing_data = []
        result = session.run(self.condition_query, patient_data=[{"data_type": d["data_type"], "value": d["value"]} for d in patient_data])
        record = result.single()
        if not record or record["result"] is None:
            missing_data = self._infer_missing_data(patient_data, self.condition_query)
            return None, [{"decision_point": self._to_json(), "missing_data": missing_data}]
        condition_met = record["result"]
        if condition_met:
            return self.if_met, []
        return self.if_not_met, []

    def _infer_missing_data(self, patient_data: List[Dict[str, str]], condition_query: str) -> List[Dict[str, any]]:
        """
        Sample "condition_query": 
        "UNWIND $patient_data AS data WITH data WHERE data.data_type = "PriorEndocrineTherapyWithin1Year" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(CASE WHEN data.value = "true" THEN true ELSE false END)) THEN true ELSE false END AS result"
        """
        available_data = {d["data_type"] for d in patient_data}
        required_fields = set()

        # Handle queries with IN clause (e.g., data.data_type IN ["ERStatus", "PRStatus", "HER2Status"])
        in_match = re.search(r'data\.data_type IN \[(.*?)\]', condition_query)
        if in_match:
            # Extract the list of data types from the IN clause
            data_types_str = in_match.group(1)
            # Split by comma and remove quotes
            data_types = [dt.strip().strip('"') for dt in data_types_str.split(',')]
            required_fields.update(data_types)
        else:
            # Handle simple queries (e.g., data.data_type = "VisceralCrisis")
            simple_match = re.search(r'data\.data_type = "([^"]+)"', condition_query)
            if simple_match:
                required_field = simple_match.group(1)
                required_fields.add(required_field)

        # Find missing fields with empty candidate values for now
        # Extract candidate values from condition_query
        candidate_values = {}
        # Look for boolean values in CASE statements
        if "CASE WHEN" in condition_query and "= 'true'" in condition_query:
            candidate_values = {field: ["true", "false"] for field in required_fields}
        # Look for specific value comparisons
        else:
            value_matches = re.findall(r'data\.value = ["\']([^"\']+)["\']', condition_query)
            if value_matches:
                candidate_values = {field: value_matches for field in required_fields}
            
        # Create missing fields list with extracted candidate values
        missing_fields = [
            {"missing_data_id": field, 
             "candidate_values": candidate_values.get(field, [])} 
            for field in required_fields if field not in available_data
        ]
        return missing_fields

    def __str__(self):
        return f"DecisionPoint({self.id}: {self.question})"

class TherapyOption:
    def __init__(self, id: str, type: str, regimen: str, outcome: str = "", next_step: str = ""):
        self.id = id
        self.type = type
        self.regimen = regimen
        self.outcome = outcome
        self.next_step = next_step

    def __str__(self):
        return f"TherapyOption({self.id}: {self.type} - {self.regimen}, Outcome: {self.outcome}, Next: {self.next_step})"

    def __eq__(self, other):
        if isinstance(other, TherapyOption):
            return self.id == other.id
        return False

class Page:
    def __init__(self, id: str, title: str):
        self.id = id
        self.title = title

    def __str__(self):
        return f"Page({self.id}: {self.title})"

class DecisionLoader:
    def __init__(self, uri: str, user: str, password: str, database: str="noe4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password), database=database)

    def close(self):
        self.driver.close()

    def load_decision_tree(self, decision_id: str, session) -> Optional[DecisionPoint]:
        query = """
        MATCH (dp:DecisionPoint {id: $decision_id})
        OPTIONAL MATCH (dp)-[:IF_MET]->(met)
        OPTIONAL MATCH (dp)-[:IF_NOT_MET]->(not_met)
        RETURN dp, met, not_met
        LIMIT 1
        """
        result = session.run(query, decision_id=decision_id)
        record = result.single()
        if not record:
            return None
        dp_node = record["dp"]
        met_node = record["met"]
        not_met_node = record["not_met"]
        if_met = self._create_node_instance(met_node, session)
        if_not_met = self._create_node_instance(not_met_node, session)
        return DecisionPoint(dp_node["id"], dp_node["question"], dp_node["condition_query"], if_met, if_not_met)

    def _create_node_instance(self, node, session) -> Optional[DecisionPoint or TherapyOption or Page]:
        if not node:
            return None
        if "TherapyOption" in node.labels:
            return TherapyOption(node["id"], node["type"], node["regimen"], node["outcome"], node["next_step"])
        if "DecisionPoint" in node.labels:
            return self.load_decision_tree(node["id"], session)
        if "Page" in node.labels:
            return Page(node["id"], node["title"])
        return None

    def process_next_step(self, current: DecisionPoint, patient_data: List[Dict[str, str]], session, steps: List[str], 
                         therapy_options: List[TherapyOption], missing_data: List[Dict[str, str]], iteration: int) -> Tuple[Optional[DecisionPoint], List[str], List[TherapyOption], List[Dict[str, str]], int]:
        print(f"current step:  {current}")
        steps.append(str(current))
        next_step, new_missing = current.evaluate(patient_data, session)
        missing_data.extend(new_missing)
        if new_missing:  # Stop immediately if new missing data is found
            return None, steps, therapy_options, missing_data, iteration

        if isinstance(next_step, TherapyOption):
            steps.append(str(next_step))
            if next_step not in therapy_options:  # Avoid duplicates
                therapy_options.append(next_step)
            # Check for next decision point (e.g., DP-BINV-21-5 for progression)
            query = """
            MATCH (t:TherapyOption {id: $therapy_id})-[:HAS_DECISION_POINT]->(dp:DecisionPoint)
            RETURN dp
            LIMIT 1
            """
            result = session.run(query, therapy_id=next_step.id)
            record = result.single()
            if record:
                return self.load_decision_tree(record["dp"]["id"], session), steps, therapy_options, missing_data, iteration
            return None, steps, therapy_options, missing_data, iteration

        elif isinstance(next_step, Page):
            steps.append(f"Transition to {next_step}")
            # Query the first decision point under the page to start the sequence
            page_id = next_step.id
            query = """
            MATCH (p:Page {id: $page_id})-[:HAS_DECISION_POINT]->(dp:DecisionPoint)
            RETURN dp
            LIMIT 1
            """
            result = session.run(query, page_id=page_id)
            record = result.single()
            if record:
                return self.load_decision_tree(record["dp"]["id"], session), steps, therapy_options, missing_data, iteration
            return None, steps, therapy_options, missing_data, iteration

        elif next_step is None:
            return None, steps, therapy_options, missing_data, iteration

        return next_step, steps, therapy_options, missing_data, iteration

    def evaluate_patient(self, patient_id: str, start_page_id: str) -> dict:
        with self.driver.session() as session:
            # Fetch patient data via the Patient node
            patient_query = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DATA]->(pd:PatientData)
            RETURN pd.data_type AS data_type, pd.value AS value
            """
            patient_result = session.run(patient_query, patient_id=patient_id)
            patient_data = [{"data_type": record["data_type"], "value": record["value"]} for record in patient_result]

            # Start with the first decision point under the specified page
            query = """
            MATCH (p:Page {id: $page_id})-[:HAS_DECISION_POINT]->(dp:DecisionPoint)
            RETURN dp
            LIMIT 1
            """
            result = session.run(query, page_id=start_page_id)
            record = result.single()
            if not record:
                return {"error": f"No decision points found for page {start_page_id}"}
            current = self.load_decision_tree(record["dp"]["id"], session)

            if not current:
                return {"error": "Decision tree not found"}
            
            steps = []
            therapy_options = []  # Collect all matching therapy options
            missing_data = []  # List of dictionaries with decision point and missing data
            max_iterations = 10  # Prevent infinite loop
            iteration = 0
            while isinstance(current, DecisionPoint) and iteration < max_iterations:
                current, steps, therapy_options, missing_data, iteration = self.process_next_step(
                    current, patient_data, session, steps, therapy_options, missing_data, iteration
                )
                if missing_data:  # Stop the loop if missing data is found
                    break
                iteration += 1
            result = {"steps": steps}
            if missing_data:
                result["missing_data"] = missing_data
            if therapy_options:
                therapies_str = "\n".join([str(t) for t in therapy_options])
                result["therapies"] = therapies_str
            return result

if __name__ == "__main__":
    # Initialize loader
    print("started ...", flush=True)
    loader = DecisionLoader("bolt://10.0.40.49:7687", "neo4j", "sacf_sacf", database='neo4j')
    # Test Case 1: BINV-20 with No Bone Disease, ER/PR-positive, HER2-negative, No Progression
    patient_id = "P010"
    print("Test Case 1: BINV-20 with No Bone Disease, ER/PR-positive, HER2-negative, No Progression")
    recommendation = loader.evaluate_patient(patient_id, "BINV-20")
    import json
    print(json.dumps(recommendation, indent=4))
    print("\n" + "-"*50 + "\n")

    # # Test Case 2: BINV-20 with Bone Disease, ER/PR-positive, HER2-negative, Progression
    # patient_id = "P002"
    # print("Test Case 2: BINV-20 with Bone Disease, ER/PR-positive, HER2-negative, Progression")
    # recommendation = loader.evaluate_patient(patient_id, "BINV-20")
    # print(json.dumps(recommendation, indent=4))
    # print("\n" + "-"*50 + "\n")

    # # Test Case 3: BINV-20 with No Bone Disease, ER/PR-negative, HER2-positive
    # patient_id = "P003"
    # print("Test Case 3: BINV-20 with No Bone Disease, ER/PR-negative, HER2-positive")
    # recommendation = loader.evaluate_patient(patient_id, "BINV-20")
    # print(json.dumps(recommendation, indent=4))
    # print("\n" + "-"*50 + "\n")

    # # Test Case 4: BINV-20 with No Bone Disease, ER/PR-positive, HER2-negative, No Progression (Missing ProgressionOrToxicity)
    # patient_id = "P004"
    # print("Test Case 4: BINV-20 with No Bone Disease, ER/PR-positive, HER2-negative, No Progression (Missing ProgressionOrToxicity)")
    # recommendation = loader.evaluate_patient(patient_id, "BINV-20")
    # print(json.dumps(recommendation, indent=4))

    # Close connection
    loader.close()