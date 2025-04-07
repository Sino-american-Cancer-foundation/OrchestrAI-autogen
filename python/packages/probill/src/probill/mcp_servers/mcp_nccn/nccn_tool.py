from neo4j import GraphDatabase
from typing import List, Dict, Optional, Tuple, Any, Union
import re
import io
import logging
from pydantic import BaseModel
from pdf2image import convert_from_path
from mcp.server.fastmcp import Image
from autogen_agentchat.utils import content_to_str

logger = logging.getLogger("evaluation")
logger.info("Starting MCP neo4j Server")
GUIDELINE_PATH="/workspaces/OrchestrAI-autogen/python/packages/probill/src/probill/mcp_servers/mcp_nccn/guideline/breast.pdf"
def is_write_query(query: str) -> bool:
    return re.search(r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD)\b", query, re.IGNORECASE) is not None

class neo4jDatabase:
    def __init__(self, neo4j_uri: str, neo4j_username: str, neo4j_password: str, neo4j_database: str):
        """Initialize connection to the neo4j database

        Args:
            neo4j_uri: URI of the Neo4j server
            neo4j_username: Username for authentication
            neo4j_password: Password for authentication
            database: Name of the database to connect to (defaults to "neo4j")
        """
        logger.debug(f"Initializing database connection to {neo4j_uri}, database: {neo4j_database}")
        print(f"Initializing database connection to {neo4j_uri}, database: {neo4j_database}",flush=True)
        d = GraphDatabase.driver(uri=neo4j_uri, auth=(neo4j_username, neo4j_password), database=neo4j_database)
        d.verify_connectivity()
        self.driver = d
        self.database = neo4j_database
        print(f"Initialized database connection to {neo4j_uri}, database: {neo4j_database}",flush=True)

    def close(self):
        """Close the database connection"""
        if hasattr(self, 'driver'):
            self.driver.close()
            logger.info("Closed Neo4j database connection")

    def _execute_query(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dictionaries"""
        logger.debug(f"Executing query on database {self.database}: {query}")
        try:
            result = self.driver.execute_query(query, params, database=self.database)
            counters = vars(result.summary.counters)
            if is_write_query(query):
                logger.debug(f"Write query affected {counters}")
                return [counters]
            else:
                results = [dict(r) for r in result.records]
                logger.debug(f"Read query returned {len(results)} rows")
                return results
        except Exception as e:
            logger.error(f"Database error executing query: {e}\n{query}")
            raise

class TherapyOption(BaseModel):
    id: str
    therapy_type: str
    regimen: str
    outcome: str = ""
    next_step: Optional[str] = ""
    _name="TherapyOption"

    def __str__(self):
        return f"TherapyOption({self.id}: {self.therapy_type} - {self.regimen}, Outcome: {self.outcome}, Next: {self.next_step})"

    def __eq__(self, other):
        if isinstance(other, TherapyOption):
            return self.id == other.id
        return False
    
    def _to_json(self):
        return self.model_dump()

    def _to_list(self):
        return [str({self._name:self.model_dump_json()})]
    
class Page(BaseModel):
    id: str
    title: str
    page_number: Optional[int]
    _name = "Page"

    class Config:
        arbitrary_types_allowed = True
    
    def _to_json(self):
        result = self.model_dump()
        try:
            images = convert_from_path(
                GUIDELINE_PATH, 
                first_page = self.page_number, 
                last_page = self.page_number
            )
            if images:
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                images[0].save(img_byte_arr, format='PNG')
                result["page_image"] = Image(data=img_byte_arr.getvalue(), format="png")                
        except Exception as e:
            logger.error(f"Error loading PDF page: {e}")        
        return result
    
    def _to_list(self):
        result = [str({self._name:self.model_dump_json()})]
        try:
            images = convert_from_path(
                GUIDELINE_PATH, 
                first_page = self.page_number, 
                last_page = self.page_number
            )
            if images:
                img_byte_arr = io.BytesIO()
                images[0].save(img_byte_arr, format='PNG')
                result.append(Image(data=img_byte_arr.getvalue(), format="png"))
        except Exception as e:
            logger.error(f"Error loading PDF page: {e}")        
        return result

    def __str__(self):
        return f"Page({self.id}: {self.title} [page: {self.page_number}])"

class DecisionPoint(BaseModel):
    id: str
    question: str = ""
    condition_query: str
    if_met: Optional[Union['TherapyOption', 'DecisionPoint', 'Page']] = None
    if_not_met: Optional[Union['TherapyOption', 'DecisionPoint', 'Page']] = None
    answer: str = "unknown"

    class ConfigDict:
        arbitrary_types_allowed = True

    def _to_json(self):
        return self.model_dump(exclude=["if_met","if_not_met","condition_query"])

    def _to_list(self):
        return [str({"DecisionPoint":self.model_dump_json(exclude=["if_met","if_not_met","condition_query"])})]


    def evaluate(self, patient_data: List[Dict[str, str]], session) -> tuple[Optional['TherapyOption' or 'DecisionPoint' or 'Page'], List[Dict[str, str]]]:
        missing_data = []
        self.answer = "unknown"
        result = session.run(self.condition_query, patient_data=[{"data_type": d["data_type"], "value": d["value"]} for d in patient_data])
        record = result.single()
        if not record or record["result"] is None:
            missing_data = self._infer_missing_data(patient_data, self.condition_query)
            self.answer = f"Patient data missed."
            return None, [{"decision_point": self._to_json(), "missing_data": missing_data}]
        condition_met = record["result"]
        if condition_met:
            self.answer = f"Condition(s) matched."
            return self.if_met, []
        self.answer = f"Condition(s) are not matched."
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
             "condition_query": condition_query} 
            for field in required_fields if field not in available_data
        ]
        return missing_fields


    # def _infer_missing_data(self, patient_data: List[Dict[str, str]], condition_query: str) -> List[str]:
    #     available_data = {d["data_type"] for d in patient_data}
    #     required_fields = set()

    #     in_match = re.search(r'data\.data_type IN \[(.*?)\]', condition_query)
    #     if in_match:
    #         data_types_str = in_match.group(1)
    #         data_types = [dt.strip().strip('"') for dt in data_types_str.split(',')]
    #         required_fields.update(data_types)
    #     else:
    #         simple_match = re.search(r'data\.data_type = "([^"]+)"', condition_query)
    #         if simple_match:
    #             required_field = simple_match.group(1)
    #             required_fields.add(required_field)

    #     missing_fields = [field for field in required_fields if field not in available_data]
    #     return missing_fields

    # def __str__(self):
    #     return f"DecisionPoint({self.id}: {self.question})"


class DecisionLoader(BaseModel):
    uri: str
    user: str
    password: str
    database: str = "neo4j"
    driver: GraphDatabase = None
    db: neo4jDatabase = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        if not self.db:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password), database=self.database)
        else:
            self.driver = self.db.driver
            
    def close(self):
        if self.driver:
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
        return DecisionPoint(
            id=dp_node["id"],
            question=dp_node["question"] or "", # Ensure question is a string, default to "" if None
            condition_query=dp_node["condition_query"],
            if_met=if_met,
            if_not_met=if_not_met
        )

    def _create_node_instance(self, node, session) -> Optional[DecisionPoint or TherapyOption or Page]:
        if not node:
            return None
        if "TherapyOption" in node.labels:
            return TherapyOption(
                id=node["id"], 
                therapy_type=node["type"], 
                regimen=node["regimen"], 
                outcome=node["outcome"], 
                next_step=node["next_step"]
            )
        if "DecisionPoint" in node.labels:
            return self.load_decision_tree(node["id"], session)
        if "Page" in node.labels:
            return Page(
                id=node["id"], 
                title=node["title"], 
                page_number=int(node["page_number"])
            )
        return None

    def process_next_step(self, current: DecisionPoint, patient_data: List[Dict[str, str]], session, steps: List[str], 
                         therapy_options: List[TherapyOption], missing_data: List[Dict[str, str]], iteration: int) -> Tuple[Optional[DecisionPoint], List[str], List[TherapyOption], List[Dict[str, str]], int]:
        next_step, new_missing = current.evaluate(patient_data, session)
        steps.extend(current._to_list())
        missing_data.extend(new_missing)
        if new_missing:  # Stop immediately if new missing data is found
            return None, steps, therapy_options, missing_data, iteration

        if isinstance(next_step, TherapyOption):
            steps.extend(next_step._to_list())
            if next_step not in therapy_options:  # Avoid duplicates
                therapy_options.append(next_step)
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
            steps.extend(next_step._to_list())
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
            patient_query = """
            MATCH (p:Patient {id: $patient_id})-[:HAS_DATA]->(pd:PatientData)
            RETURN pd.data_type AS data_type, pd.value AS value
            """
            patient_result = session.run(patient_query, patient_id=patient_id)
            patient_data = [{"data_type": record["data_type"], "value": record["value"]} for record in patient_result]

            query = """
            MATCH (p:Page {id: $page_id})-[:HAS_DECISION_POINT]->(dp:DecisionPoint)
            RETURN dp, p
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
            start_page = Page(id=record["p"]["id"], title=record["p"]["title"], page_number=int(record["p"]["page_number"]))
            steps.extend(start_page._to_list())

            therapy_options = []
            missing_data = []
            max_iterations = 10
            iteration = 0
            while isinstance(current, DecisionPoint) and iteration < max_iterations:
                current, steps, therapy_options, missing_data, iteration = self.process_next_step(
                    current, patient_data, session, steps, therapy_options, missing_data, iteration
                )
                if missing_data:
                    break
                iteration += 1
            final_result = steps

            if missing_data:
                
                final_result.append(str({"MissingData":content_to_str(missing_data)}))
                
            if therapy_options:
                therapies_str = "\n".join([str(t) for t in therapy_options])
                final_result.append(str({"Therapies":therapies_str}))
            return final_result