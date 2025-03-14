import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Define the data classes as provided
@dataclass
class PatientCase:
    patient_id: str
    demographics: dict
    medical_history: List[dict]  # Adjusted to match query: List[dict] instead of dict
    radiology_report: dict
    pathology_report: dict
    patient_preferences: Optional[dict] = None
    insurance_status: Optional[dict] = None

@dataclass
class TreatmentRecommendation:
    patient_id: str
    treatments: List[dict]
    rationale: str
    confidence_score: float
    needs_human_review: bool

# Define the PolicyNetwork with LSTM for sequential data
class PolicyNetwork(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim=64):
        super(PolicyNetwork, self).__init__()
        self.lstm = nn.LSTM(state_dim, hidden_dim, num_layers=1, batch_first=True)
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, action_dim)

    def forward(self, state_sequence):
        # Process sequence with LSTM, take the last hidden state
        _, (hn, _) = self.lstm(state_sequence)
        x = hn[-1]  # Last hidden state
        x = F.relu(self.fc1(x))
        logits = self.fc2(x)
        return logits

# Feature extraction function to convert PatientCase to a state sequence
def extract_features(patient_case: PatientCase, seq_len=3):
    """Convert PatientCase into a tensor of shape (1, seq_len, state_dim)."""
    # Static features
    age = float(patient_case.demographics.get("age", 0))
    sex = 1.0 if patient_case.demographics.get("sex", "male") == "male" else 0.0

    tumor_size = float(patient_case.radiology_report.get("tumor_size", 0.0))
    location = 0.0 if patient_case.radiology_report.get("location", "left") == "left" else 1.0

    grade = float(patient_case.pathology_report.get("grade", 0.0))
    biomarkers = 1.0 if "positive" in patient_case.pathology_report.get("biomarkers", []) else 0.0

    # Dynamic features from medical history
    event_types = {"surgery": 0, "chemotherapy": 1, "none": 2}
    index_date = datetime.now()
    state_sequence = []

    for event in patient_case.medical_history:
        event_type_str = event.get("event", "none")
        event_type_idx = event_types.get(event_type_str, 2)  # Default to "none"
        event_date_str = event.get("date", "2020-01-01")
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        time_to_index = (index_date - event_date).days / 365.0  # Time in years

        # One-hot encode event type (3 possible types)
        event_one_hot = [0.0] * 3
        event_one_hot[event_type_idx] = 1.0

        # State vector: [age, sex, event_one_hot, time_to_index, tumor_size, location, grade, biomarkers]
        state_vector = [age, sex] + event_one_hot + [time_to_index, tumor_size, location, grade, biomarkers]
        state_sequence.append(state_vector)

    # Pad sequence to seq_len with zeros
    state_dim = 10  # Total features per state vector
    while len(state_sequence) < seq_len:
        state_sequence.append([0.0] * state_dim)
    state_sequence = state_sequence[-seq_len:]  # Truncate to seq_len if too long

    # Convert to tensor: (1, seq_len, state_dim)
    return torch.tensor(state_sequence, dtype=torch.float32).unsqueeze(0)

# Function to map action index to treatment
def action_to_treatment(action_index):
    """Map PolicyNetwork action to a treatment dictionary."""
    treatment_map = {
        0: {"type": "continue_current"},
        1: {"type": "switch_to_new"},
        2: {"type": "stop_treatment"}
    }
    return treatment_map.get(action_index, {"type": "unknown"})

# Main function to connect PatientCase to TreatmentRecommendation via PolicyNetwork
def generate_treatment_recommendation(policy_net: PolicyNetwork, patient_case: PatientCase):
    """Generate a TreatmentRecommendation from a PatientCase using the PolicyNetwork."""
    # Extract state sequence
    state_sequence = extract_features(patient_case)

    # Get action logits from PolicyNetwork
    logits = policy_net(state_sequence)
    probs = F.softmax(logits, dim=-1)
    action_index = torch.argmax(probs, dim=-1).item()
    confidence_score = probs[0, action_index].item()

    # Map action to treatment
    treatment = action_to_treatment(action_index)

    # Create TreatmentRecommendation
    recommendation = TreatmentRecommendation(
        patient_id=patient_case.patient_id,
        treatments=[treatment],
        rationale="Decision based on patient history and clinical data.",
        confidence_score=confidence_score,
        needs_human_review=confidence_score < 0.8
    )
    return recommendation

# Example usage
if __name__ == "__main__":
    # Sample PatientCase
    sample_patient = PatientCase(
        patient_id="123",
        demographics={"age": 65, "sex": "male"},
        medical_history=[
            {"event": "surgery", "date": "2020-01-01"},
            {"event": "chemotherapy", "date": "2021-06-15"}
        ],
        radiology_report={"tumor_size": 2.5, "location": "left lung"},
        pathology_report={"grade": 3, "biomarkers": ["positive"]}
    )

    # Initialize PolicyNetwork
    state_dim = 10  # Number of features in each state vector
    action_dim = 3  # Number of possible treatment actions
    policy_net = PolicyNetwork(state_dim, action_dim)

    # Generate treatment recommendation
    recommendation = generate_treatment_recommendation(policy_net, sample_patient)
    print(f"Patient ID: {recommendation.patient_id}")
    print(f"Treatments: {recommendation.treatments}")
    print(f"Rationale: {recommendation.rationale}")
    print(f"Confidence Score: {recommendation.confidence_score}")
    print(f"Needs Human Review: {recommendation.needs_human_review}")