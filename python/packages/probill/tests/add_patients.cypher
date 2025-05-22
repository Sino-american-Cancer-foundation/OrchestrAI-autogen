// Merge Patient nodes and their PatientData
MERGE (p001:Patient {id: 'P001'})
ON CREATE SET p001.vocabulary_id = 'sacf',
              p001.concept_name = 'Patient P001',
              p001.domain_id = 'patient',
              p001.concept_class_id = 'Patient'
MERGE (p001)-[:HAS_DATA]->(pd001_1:PatientData {data_type: 'BoneDiseasePresent', value: 'false'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'BoneDiseasePresent',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_2:PatientData {data_type: 'ERStatus', value: 'positive'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'ERStatus',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_3:PatientData {data_type: 'PRStatus', value: 'positive'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'PRStatus',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_4:PatientData {data_type: 'HER2Status', value: 'negative'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'HER2Status',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_5:PatientData {data_type: 'VisceralCrisis', value: 'false'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'VisceralCrisis',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_6:PatientData {data_type: 'PriorEndocrineTherapyWithin1Year', value: 'false'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'PriorEndocrineTherapyWithin1Year',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_7:PatientData {data_type: 'MenopausalStatus', value: 'postmenopausal'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'MenopausalStatus',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'
MERGE (p001)-[:HAS_DATA]->(pd001_8:PatientData {data_type: 'ProgressionOrToxicity', value: 'false'})
ON CREATE SET pd001_1.vocabulary_id = 'sacf',
              pd001_1.concept_name = 'ProgressionOrToxicity',
              pd001_1.domain_id = 'condition',
              pd001_1.concept_class_id = 'Condition'

MERGE (p002:Patient {id: 'P002'})
MERGE (p002)-[:HAS_DATA]->(pd002_1:PatientData {patient_id: 'P002', data_type: 'BoneDiseasePresent', value: 'true'})
MERGE (p002)-[:HAS_DATA]->(pd002_2:PatientData {patient_id: 'P002', data_type: 'ERStatus', value: 'positive'})
MERGE (p002)-[:HAS_DATA]->(pd002_3:PatientData {patient_id: 'P002', data_type: 'PRStatus', value: 'positive'})
MERGE (p002)-[:HAS_DATA]->(pd002_4:PatientData {patient_id: 'P002', data_type: 'HER2Status', value: 'negative'})
MERGE (p002)-[:HAS_DATA]->(pd002_5:PatientData {patient_id: 'P002', data_type: 'VisceralCrisis', value: 'false'})
MERGE (p002)-[:HAS_DATA]->(pd002_6:PatientData {patient_id: 'P002', data_type: 'PriorEndocrineTherapyWithin1Year', value: 'false'})
MERGE (p002)-[:HAS_DATA]->(pd002_7:PatientData {patient_id: 'P002', data_type: 'MenopausalStatus', value: 'postmenopausal'})
MERGE (p002)-[:HAS_DATA]->(pd002_8:PatientData {patient_id: 'P002', data_type: 'ProgressionOrToxicity', value: 'true'})
MERGE (p002)-[:HAS_DATA]->(pd002_9:PatientData {patient_id: 'P002', data_type: 'EndocrineRefractory', value: 'false'})

MERGE (p003:Patient {id: 'P003'})
MERGE (p003)-[:HAS_DATA]->(pd003_1:PatientData {patient_id: 'P003', data_type: 'BoneDiseasePresent', value: 'false'})
MERGE (p003)-[:HAS_DATA]->(pd003_2:PatientData {patient_id: 'P003', data_type: 'ERStatus', value: 'negative'})
MERGE (p003)-[:HAS_DATA]->(pd003_3:PatientData {patient_id: 'P003', data_type: 'PRStatus', value: 'negative'})
MERGE (p003)-[:HAS_DATA]->(pd003_4:PatientData {patient_id: 'P003', data_type: 'HER2Status', value: 'positive'})
MERGE (p003)-[:HAS_DATA]->(pd003_5:PatientData {patient_id: 'P003', data_type: 'ProgressionOrToxicity', value: 'true'})

MERGE (p004:Patient {id: 'P004'})
MERGE (p004)-[:HAS_DATA]->(pd004_1:PatientData {patient_id: 'P004', data_type: 'BoneDiseasePresent', value: 'false'})
MERGE (p004)-[:HAS_DATA]->(pd004_2:PatientData {patient_id: 'P004', data_type: 'ERStatus', value: 'positive'})
MERGE (p004)-[:HAS_DATA]->(pd004_3:PatientData {patient_id: 'P004', data_type: 'PRStatus', value: 'positive'})
MERGE (p004)-[:HAS_DATA]->(pd004_4:PatientData {patient_id: 'P004', data_type: 'HER2Status', value: 'negative'})
MERGE (p004)-[:HAS_DATA]->(pd004_5:PatientData {patient_id: 'P004', data_type: 'VisceralCrisis', value: 'false'})
MERGE (p004)-[:HAS_DATA]->(pd004_6:PatientData {patient_id: 'P004', data_type: 'PriorEndocrineTherapyWithin1Year', value: 'false'})
MERGE (p004)-[:HAS_DATA]->(pd004_7:PatientData {patient_id: 'P004', data_type: 'MenopausalStatus', value: 'postmenopausal'})