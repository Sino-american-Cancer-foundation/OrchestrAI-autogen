from pydantic import BaseModel

class NCCNGuideline(BaseModel):
    
    def __init__(self, page_id):
        """
        Initialize the guideline with a page identifier.

        Parameters:
        - page_id (str): Identifier for the NCCN page (e.g., 'BINV-7').
        """
        self.page_id = page_id
        self.footnotes = {}  # Dictionary to store footnote conditions and modifications

    def add_footnote(self, footnote_id, condition_func, treatment_modification):
        """
        Add a footnote to modify treatment recommendations.

        Parameters:
        - footnote_id (str): Unique identifier for the footnote (e.g., 'kk').
        - condition_func (callable): Function that takes patient_data and returns True if the footnote applies.
        - treatment_modification (str or callable): Modified recommendation or a function to generate it.
        """
        self.footnotes[footnote_id] = (condition_func, treatment_modification)

    def get_treatment_recommendation(self, patient_data):
        """
        Abstract method to get treatment recommendation. Subclasses must override this.

        Parameters:
        - patient_data (dict): Patient-specific data (e.g., {'tumor_size': 0.7, 'histology': 'low-grade'}).

        Returns:
        - str: Treatment recommendation.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def apply_footnotes(self, patient_data, base_recommendation):
        """
        Apply applicable footnotes to modify the base recommendation.

        Parameters:
        - patient_data (dict): Patient data to evaluate footnote conditions.
        - base_recommendation (str): Initial recommendation before footnote modifications.

        Returns:
        - str: Modified recommendation if footnotes apply, otherwise the base recommendation.
        """
        for footnote_id, (condition_func, modification) in self.footnotes.items():
            if condition_func(patient_data):
                if callable(modification):
                    return modification(base_recommendation)
                return modification
        return base_recommendation

    def format_output(self, treatment):
        """
        Standardize output with treatment and follow-up.

        Parameters:
        - treatment (str): Treatment recommendation.

        Returns:
        - str: Formatted output including follow-up.
        """
        follow_up = "Follow-Up (BINV-17)"  # Default follow-up, can be overridden
        return f"{treatment}. Then, {follow_up}."