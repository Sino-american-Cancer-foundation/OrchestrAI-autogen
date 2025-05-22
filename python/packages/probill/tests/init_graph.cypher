
// Merge Page node for BINV-20
MERGE (p20:Page {id: 'BINV-20'})
ON CREATE SET p20.title = 'SYSTEMIC TREATMENT OF RECURRENT UNRESECTABLE (LOCAL OR REGIONAL) OR STAGE IV (M1) DISEASE',
              p20.vocabulary_id = 'sacf',
              p20.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease',
              p20.domain_id = 'guideline',
              p20.concept_class_id = 'GuidelinePage',
              p20.page_number = 33
            

// BINV-20 Decision Points and Therapy Options
MERGE (dp20_1:DecisionPoint {id: 'DP-BINV-20-1'})
ON CREATE SET dp20_1.question = 'Does the patient have bone disease?',
              dp20_1.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "BoneDiseasePresent" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp20_1.vocabulary_id = 'sacf',
              dp20_1.concept_name = 'Bone Disease',
              dp20_1.domain_id = 'guideline',
              dp20_1.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t20_1:TherapyOption {id: 'T-BINV-20-1'})
ON CREATE SET t20_1.type = 'Bone Disease Therapy',
              t20_1.regimen = 'Denosumab, zoledronic acid, or pamidronate (all with calcium and vitamin D supplementation)',
              t20_1.outcome = 'In addition to systemic therapy if bone metastases present, expected survival >= 3 months, and renal function adequate; dental exam and monitor for osteonecrosis of the jaw',
              t20_1.vocabulary_id = 'sacf',
              t20_1.concept_name = 'Bone Disease Therapy: Denosumab, zoledronic acid, or pamidronate (all with calcium and vitamin D supplementation)',
              t20_1.domain_id = 'guideline',
              t20_1.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp20_2:DecisionPoint {id: 'DP-BINV-20-2'})
ON CREATE SET dp20_2.question = 'Is the patient ER- and/or PR-positive and HER2-negative?',
              dp20_2.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type IN ["ERStatus", "PRStatus", "HER2Status"] WITH COLLECT({type: data.data_type, value: data.value}) AS data_list RETURN CASE WHEN SIZE(data_list) = 0 THEN null WHEN ANY(data IN data_list WHERE data.type = "ERStatus" AND data.value = "positive") OR ANY(data IN data_list WHERE data.type = "PRStatus" AND data.value = "positive") AND ANY(data IN data_list WHERE data.type = "HER2Status" AND data.value = "negative") THEN true ELSE false END AS result',
              dp20_2.vocabulary_id = 'sacf',
              dp20_2.concept_name = 'ER- and/or PR-positive and HER2-negative',
              dp20_2.domain_id = 'guideline',
              dp20_2.concept_class_id = 'GuidelineDecisionPoint'

MERGE (dp20_3:DecisionPoint {id: 'DP-BINV-20-3'})
ON CREATE SET dp20_3.question = 'Is the patient ER- and/or PR-positive and HER2-positive?',
              dp20_3.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type IN ["ERStatus", "PRStatus", "HER2Status"] WITH COLLECT({type: data.data_type, value: data.value}) AS data_list RETURN CASE WHEN SIZE(data_list) = 0 THEN null WHEN ANY(data IN data_list WHERE data.type = "ERStatus" AND data.value = "positive") OR ANY(data IN data_list WHERE data.type = "PRStatus" AND data.value = "positive") AND ANY(data IN data_list WHERE data.type = "HER2Status" AND data.value = "positive") THEN true ELSE false END AS result',
              dp20_3.vocabulary_id = 'sacf',
              dp20_3.concept_name = 'ER- and/or PR-positive and HER2-positive',
              dp20_3.domain_id = 'guideline',
              dp20_3.concept_class_id = 'GuidelineDecisionPoint'

MERGE (dp20_4:DecisionPoint {id: 'DP-BINV-20-4'})
ON CREATE SET dp20_4.question = 'Is the patient ER- and PR-negative and HER2-positive?',
              dp20_4.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type IN ["ERStatus", "PRStatus", "HER2Status"] WITH COLLECT({type: data.data_type, value: data.value}) AS data_list RETURN CASE WHEN SIZE(data_list) = 0 THEN null WHEN ANY(data IN data_list WHERE data.type = "ERStatus" AND data.value = "negative") AND ANY(data IN data_list WHERE data.type = "PRStatus" AND data.value = "negative") AND ANY(data IN data_list WHERE data.type = "HER2Status" AND data.value = "positive") THEN true ELSE false END AS result',
              dp20_4.vocabulary_id = 'sacf',
              dp20_4.concept_name = 'ER- and PR-negative and HER2-positive',
              dp20_4.domain_id = 'guideline',
              dp20_4.concept_class_id = 'GuidelineDecisionPoint'

MERGE (dp20_5:DecisionPoint {id: 'DP-BINV-20-5'})
ON CREATE SET dp20_5.question = 'Is the patient ER- and PR-negative and HER2-negative?',
              dp20_5.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type IN ["ERStatus", "PRStatus", "HER2Status"] WITH COLLECT({type: data.data_type, value: data.value}) AS data_list RETURN CASE WHEN SIZE(data_list) = 0 THEN null WHEN ANY(data IN data_list WHERE data.type = "ERStatus" AND data.value = "negative") AND ANY(data IN data_list WHERE data.type = "PRStatus" AND data.value = "negative") AND ANY(data IN data_list WHERE data.type = "HER2Status" AND data.value = "negative") THEN true ELSE false END AS result',
              dp20_5.vocabulary_id = 'sacf',
              dp20_5.concept_name = 'ER- and PR-negative and HER2-negative',
              dp20_5.domain_id = 'guideline',
              dp20_5.concept_class_id = 'GuidelineDecisionPoint'

// Merge Page nodes for transitions
MERGE (p21:Page {id: 'BINV-21'})
ON CREATE SET p21.title = 'SYSTEMIC TREATMENT OF RECURRENT UNRESECTABLE (LOCAL OR REGIONAL) OR STAGE IV (M1) DISEASE: ER- AND/OR PR-POSITIVE; HER2-NEGATIVE',
              p21.vocabulary_id = 'sacf',
              p21.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease: ER- and/or PR-positive; HER2-negative',
              p21.domain_id = 'guideline',
              p21.concept_class_id = 'GuidelinePage',
              p21.page_number = 34

MERGE (p23:Page {id: 'BINV-23'})
ON CREATE SET p23.title = 'SYSTEMIC TREATMENT OF RECURRENT UNRESECTABLE (LOCAL OR REGIONAL) OR STAGE IV (M1) DISEASE: ER- AND/OR PR-POSITIVE; HER2-POSITIVE',
              p23.vocabulary_id = 'sacf',
              p23.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease: ER- and/or PR-positive; HER2-positive',
              p23.domain_id = 'guideline',
              p23.concept_class_id = 'GuidelinePage',
              p23.page_number = 36

MERGE (p25:Page {id: 'BINV-25'})
ON CREATE SET p25.title = 'SYSTEMIC TREATMENT OF RECURRENT UNRESECTABLE (LOCAL OR REGIONAL) OR STAGE IV (M1) DISEASE: ER- AND PR-NEGATIVE; HER2-POSITIVE',
              p25.vocabulary_id = 'sacf',
              p25.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease: ER- and PR-negative; HER2-positive',
              p25.domain_id = 'guideline',
              p25.concept_class_id = 'GuidelinePage',
              p25.page_number = 38

MERGE (p26:Page {id: 'BINV-26'})
ON CREATE SET p26.title = 'SYSTEMIC TREATMENT OF RECURRENT UNRESECTABLE (LOCAL OR REGIONAL) OR STAGE IV (M1) DISEASE: ER- AND PR-NEGATIVE; HER2-NEGATIVE',
              p26.vocabulary_id = 'sacf',
              p26.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease: ER- and PR-negative; HER2-negative',
              p26.domain_id = 'guideline',
              p26.concept_class_id = 'GuidelinePage',
              p26.page_number = 39

// BINV-20 Relationships
MERGE (p20)-[:HAS_DECISION_POINT]->(dp20_1)
MERGE (dp20_1)-[:IF_MET]->(t20_1)
MERGE (dp20_1)-[:IF_NOT_MET]->(dp20_2)
MERGE (t20_1)-[:HAS_DECISION_POINT]->(dp20_2)
MERGE (dp20_2)-[:IF_MET]->(p21)
MERGE (dp20_2)-[:IF_NOT_MET]->(dp20_3)
MERGE (dp20_3)-[:IF_MET]->(p23)
MERGE (dp20_3)-[:IF_NOT_MET]->(dp20_4)
MERGE (dp20_4)-[:IF_MET]->(p25)
MERGE (dp20_4)-[:IF_NOT_MET]->(dp20_5)
MERGE (dp20_5)-[:IF_MET]->(p26)

// BINV-21 Decision Points and Therapy Options
MERGE (dp21_1:DecisionPoint {id: 'DP-BINV-21-1'})
ON CREATE SET dp21_1.question = 'Does the patient have a visceral crisis?',
              dp21_1.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "VisceralCrisis" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp21_1.vocabulary_id = 'sacf',
              dp21_1.concept_name = 'Visceral Crisis',
              dp21_1.domain_id = 'guideline',
              dp21_1.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t21_1:TherapyOption {id: 'T-BINV-21-1'})
ON CREATE SET t21_1.type = 'Systemic Therapy',
              t21_1.regimen = 'Consider initial systemic therapy (BINV-Q)',
              t21_1.outcome = 'Continue until progression or unacceptable toxicity',
              t21_1.vocabulary_id = 'sacf',
              t21_1.concept_name = 'Systemic Therapy: Consider initial systemic therapy (BINV-Q)',
              t21_1.domain_id = 'guideline',
              t21_1.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp21_2:DecisionPoint {id: 'DP-BINV-21-2'})
ON CREATE SET dp21_2.question = 'Has the patient had prior endocrine therapy within 1 year?',
              dp21_2.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "PriorEndocrineTherapyWithin1Year" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(CASE WHEN data.value = "true" THEN true ELSE false END)) THEN true ELSE false END AS result',
              dp21_2.vocabulary_id = 'sacf',
              dp21_2.concept_name = 'Prior Endocrine Therapy Within 1 Year',
              dp21_2.domain_id = 'guideline',
              dp21_2.concept_class_id = 'GuidelineDecisionPoint'

MERGE (dp21_3:DecisionPoint {id: 'DP-BINV-21-3'})
ON CREATE SET dp21_3.description = 'Is the patient premenopausal with prior therapy within 1 year?',
              dp21_3.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "MenopausalStatus" AND data.value = "premenopausal" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN true THEN true ELSE false END AS result',
              dp21_3.vocabulary_id = 'sacf',
              dp21_3.concept_name = 'Premenopausal with Prior Therapy Within 1 Year',
              dp21_3.domain_id = 'guideline',
              dp21_3.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t21_2:TherapyOption {id: 'T-BINV-21-2'})
ON CREATE SET t21_2.type = 'Ovarian Ablation/Suppression + Systemic Therapy',
              t21_2.regimen = 'See BINV-P',
              t21_2.outcome = 'Continue until progression or unacceptable toxicity',
              t21_2.vocabulary_id = 'sacf',
              t21_2.concept_name = 'Ovarian Ablation/Suppression + Systemic Therapy: See BINV-P',
              t21_2.domain_id = 'guideline',
              t21_2.concept_class_id = 'GuidelineTherapyOption'

MERGE (t21_3:TherapyOption {id: 'T-BINV-21-3'})
ON CREATE SET t21_3.type = 'Systemic Therapy',
              t21_3.regimen = 'See BINV-P',
              t21_3.outcome = 'Continue until progression or unacceptable toxicity',
              t21_3.vocabulary_id = 'sacf',
              t21_3.concept_name = 'Systemic Therapy: See BINV-P',
              t21_3.domain_id = 'guideline',
              t21_3.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp21_4:DecisionPoint {id: 'DP-BINV-21-4'})
ON CREATE SET dp21_4.question = 'Is the patient postmenopausal with no prior therapy within 1 year?',
              dp21_4.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "MenopausalStatus" AND data.value = "postmenopausal" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN true THEN true ELSE false END AS result',
              dp21_4.vocabulary_id = 'sacf',
              dp21_4.concept_name = 'Postmenopausal with No Prior Therapy Within 1 Year',
              dp21_4.domain_id = 'guideline',
              dp21_4.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t21_4:TherapyOption {id: 'T-BINV-21-4'})
ON CREATE SET t21_4.type = 'Ovarian Ablation/Suppression + Systemic Therapy',
              t21_4.regimen = 'See BINV-P',
              t21_4.outcome = 'Continue until progression or unacceptable toxicity',
              t21_4.vocabulary_id = 'sacf',
              t21_4.concept_name = 'Ovarian Ablation/Suppression + Systemic Therapy: See BINV-P',
              t21_4.domain_id = 'guideline',
              t21_4.concept_class_id = 'GuidelineTherapyOption'

MERGE (t21_5:TherapyOption {id: 'T-BINV-21-5'})
ON CREATE SET t21_5.type = 'Selective ER Modulators',
              t21_5.regimen = 'See BINV-P',
              t21_5.outcome = 'Continue until progression or unacceptable toxicity',
              t21_5.vocabulary_id = 'sacf',
              t21_5.concept_name = 'Systemic Treatment of Recurrent Unresectable (Local or Regional) or Stage IV (M1) Disease',
              t21_5.domain_id = 'guideline',
              t21_5.concept_class_id = 'GuidelinePage'

MERGE (t21_6:TherapyOption {id: 'T-BINV-21-6'})
ON CREATE SET t21_6.type = 'Systemic Therapy',
              t21_6.regimen = 'See BINV-P',
              t21_6.outcome = 'Continue until progression or unacceptable toxicity',
              t21_6.vocabulary_id = 'sacf',
              t21_6.concept_name = 'Systemic Therapy: See BINV-P',
              t21_6.domain_id = 'guideline',
              t21_6.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp21_5:DecisionPoint {id: 'DP-BINV-21-5'})
ON CREATE SET dp21_5.question = 'Has there been progression or unacceptable toxicity?',
              dp21_5.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "ProgressionOrToxicity" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp21_5.vocabulary_id = 'sacf',
              dp21_5.concept_name = 'Progression or Unacceptable Toxicity',
              dp21_5.domain_id = 'guideline',
              dp21_5.concept_class_id = 'GuidelineDecisionPoint'

// Merge Page node for BINV-22
MERGE (p22:Page {id: 'BINV-22'})
ON CREATE SET p22.title = 'PROGRESSION OR UNACCEPTABLE TOXICITY ON FIRST-LINE THERAPY (ENDOCRINE OR SYSTEMIC)',
              p22.vocabulary_id = 'sacf',
              p22.concept_name = 'Progression or Unacceptable Toxicity on First-Line Therapy (Endocrine or Systemic)',
              p22.domain_id = 'guideline',
              p22.concept_class_id = 'GuidelinePage'

// BINV-22 Decision Points and Therapy Options
MERGE (dp22_1:DecisionPoint {id: 'DP-BINV-22-1'})
ON CREATE SET dp22_1.question = 'Does the patient have a visceral crisis?',
              dp22_1.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "VisceralCrisis" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp22_1.vocabulary_id = 'sacf',
              dp22_1.concept_name = 'Visceral Crisis',
              dp22_1.domain_id = 'guideline',
              dp22_1.concept_class_id = 'GuidelineDecisionPoint'

MERGE (dp22_2:DecisionPoint {id: 'DP-BINV-22-2'})
ON CREATE SET dp22_2.question = 'Is the patient endocrine therapy refractory?',
              dp22_2.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "EndocrineRefractory" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp22_2.vocabulary_id = 'sacf',
              dp22_2.concept_name = 'Endocrine Therapy Refractory',
              dp22_2.domain_id = 'guideline',
              dp22_2.concept_class_id = 'GuidelinePage'

MERGE (t22_1:TherapyOption {id: 'T-BINV-22-1'})
ON CREATE SET t22_1.type = 'Alternate Endocrine Therapy ± Targeted Therapy',
              t22_1.regimen = 'See BINV-P',
              t22_1.outcome = 'Continue until further progression or toxicity',
              t22_1.vocabulary_id = 'sacf',
              t22_1.concept_name = 'Alternate Endocrine Therapy ± Targeted Therapy: See BINV-P',
              t22_1.domain_id = 'guideline',
              t22_1.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp22_3:DecisionPoint {id: 'DP-BINV-22-3'})
ON CREATE SET dp22_3.question = 'Is there no clinical benefit after up to 3 sequential endocrine therapy regimens or symptomatic visceral disease?',
              dp22_3.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "ClinicalBenefitAfter3Endocrine" OR data.data_type = "SymptomaticVisceralDisease" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp22_3.vocabulary_id = 'sacf',
              dp22_3.concept_name = 'No Clinical Benefit After 3 Sequential Endocrine Therapy Regimens or Symptomatic Visceral Disease',
              dp22_3.domain_id = 'guideline',
              dp22_3.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t22_2:TherapyOption {id: 'T-BINV-22-2'})
ON CREATE SET t22_2.type = 'Systemic Therapy',
              t22_2.regimen = 'See BINV-Q',
              t22_2.outcome = 'Continue with reassessment',
              t22_2.vocabulary_id = 'sacf',
              t22_2.concept_name = 'Systemic Therapy: See BINV-Q',
              t22_2.domain_id = 'guideline',
              t22_2.concept_class_id = 'GuidelineTherapyOption'

MERGE (t22_3:TherapyOption {id: 'T-BINV-22-3'})
ON CREATE SET t22_3.type = 'Alternate Endocrine Therapy',
              t22_3.regimen = 'See BINV-P',
              t22_3.outcome = 'Monitor for progression or toxicity',
              t22_3.vocabulary_id = 'sacf',
              t22_3.concept_name = 'Alternate Endocrine Therapy: See BINV-P',
              t22_3.domain_id = 'guideline',
              t22_3.concept_class_id = 'GuidelineTherapyOption'

MERGE (dp22_4:DecisionPoint {id: 'DP-BINV-22-4'})
ON CREATE SET dp22_4.question = 'Is the patient a candidate for multiple lines of systemic therapy?',
              dp22_4.condition_query = 'UNWIND $patient_data AS data WITH data WHERE data.data_type = "CandidateForMultipleSystemic" RETURN CASE WHEN COUNT(data) = 0 THEN null WHEN HEAD(COLLECT(data.value)) = "true" THEN true ELSE false END AS result',
              dp22_4.vocabulary_id = 'sacf',
              dp22_4.concept_name = 'Candidate for Multiple Lines of Systemic Therapy',
              dp22_4.domain_id = 'guideline',
              dp22_4.concept_class_id = 'GuidelineDecisionPoint'

MERGE (t22_4:TherapyOption {id: 'T-BINV-22-4'})
ON CREATE SET t22_4.type = 'Alternate Systemic Therapy',
              t22_4.regimen = 'See BINV-Q',
              t22_4.outcome = 'Continue with reassessment',
              t22_4.vocabulary_id = 'sacf',
              t22_4.concept_name = 'Alternate Systemic Therapy: See BINV-Q',
              t22_4.domain_id = 'guideline',
              t22_4.concept_class_id = 'GuidelineTherapyOption'

MERGE (t22_5:TherapyOption {id: 'T-BINV-22-5'})
ON CREATE SET t22_5.type = 'Additional Systemic Therapy',
              t22_5.regimen = 'Assess risks, benefits, and patient preferences',
              t22_5.outcome = 'Continue with evaluation',
              t22_5.vocabulary_id = 'sacf',
              t22_5.concept_name = 'Additional Systemic Therapy: Assess risks, benefits, and patient preferences',
              t22_5.domain_id = 'guideline',
              t22_5.concept_class_id = 'GuidelineTherapyOption'

MERGE (t22_6:TherapyOption {id: 'T-BINV-22-6'})
ON CREATE SET t22_6.type = 'Supportive Care',
              t22_6.regimen = 'See NCCN Palliative/Supportive Care Guidelines',
              t22_6.outcome = 'Focus on quality of life',
              t22_6.vocabulary_id = 'sacf',
              t22_6.concept_name = 'Supportive Care: See NCCN Palliative/Supportive Care Guidelines',
              t22_6.domain_id = 'guideline',
              t22_6.concept_class_id = 'GuidelineTherapyOption'

// Relationships for BINV-21
MERGE (p21)-[:HAS_DECISION_POINT]->(dp21_1)
MERGE (dp21_1)-[:IF_MET]->(t21_1)
MERGE (dp21_1)-[:IF_NOT_MET]->(dp21_2)
MERGE (dp21_2)-[:IF_MET]->(dp21_3)
MERGE (dp21_2)-[:IF_NOT_MET]->(dp21_4)
MERGE (dp21_3)-[:IF_MET]->(t21_2)
MERGE (dp21_3)-[:IF_NOT_MET]->(t21_3)
MERGE (dp21_4)-[:IF_MET]->(t21_6)
MERGE (dp21_4)-[:IF_NOT_MET]->(t21_4)
MERGE (dp21_4)-[:ALTERNATIVE]->(t21_5)
MERGE (t21_1)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (t21_2)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (t21_3)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (t21_4)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (t21_5)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (t21_6)-[:HAS_DECISION_POINT]->(dp21_5)
MERGE (dp21_5)-[:IF_MET]->(p22)

// Relationships for BINV-22
MERGE (p22)-[:HAS_DECISION_POINT]->(dp22_1)
MERGE (dp22_1)-[:IF_MET]->(t22_4)
MERGE (dp22_1)-[:IF_NOT_MET]->(dp22_2)
MERGE (dp22_2)-[:IF_MET]->(dp22_3)
MERGE (dp22_2)-[:IF_NOT_MET]->(t22_1)
MERGE (dp22_3)-[:IF_MET]->(t22_2)
MERGE (dp22_3)-[:IF_NOT_MET]->(t22_3)
MERGE (dp22_1)-[:IF_NOT_MET]->(dp22_4)
MERGE (dp22_4)-[:IF_MET]->(t22_5)
MERGE (dp22_4)-[:IF_NOT_MET]->(t22_6)

