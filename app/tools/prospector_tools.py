# app/tools/prospector_tools.py
import yaml
from pathlib import Path
from typing import Dict, Any

# Load the ICP config once to be used by all tools
def load_icp_config() -> Dict[str, Any]:
    # This path navigates from app/tools/ -> app/ -> project_root/ -> configs/
    config_path = Path(__file__).parent.parent.parent / "configs" / "icp.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

ICP_CONFIG = load_icp_config()

def check_industry(industry: str) -> bool:
    """Returns True if the industry is in the target list, otherwise False."""
    return industry in ICP_CONFIG['firmographics']['target_industries']

def check_employee_count(employee_count: int) -> bool:
    """Returns True if the employee count is within the ideal range, otherwise False."""
    if not isinstance(employee_count, int):
        return False
    min_count = ICP_CONFIG['firmographics']['employee_count']['min']
    max_count = ICP_CONFIG['firmographics']['employee_count']['max']
    return min_count <= employee_count <= max_count

def check_location(location: str) -> bool:
    """Returns True if the location is in the target list, otherwise False."""
    return location in ICP_CONFIG['firmographics']['locations']

def check_job_title(job_title: str) -> bool:
    """Returns True if the job title is a target senior leader, otherwise False."""
    title_lower = job_title.lower()
    return any(target.lower() in title_lower for target in ICP_CONFIG['persona']['job_titles'])

def check_excluded_job_title(job_title: str) -> bool:
    """Returns True if the job title is an excluded junior role, otherwise False."""
    title_lower = job_title.lower()
    return any(excluded.lower() in title_lower for excluded in ICP_CONFIG['persona']['excluded_titles'])

def calculate_final_score(tool_results: Dict[str, bool]) -> tuple[int, str, str]:
    """Calculates the final score, status, and a reasoning string based on the tool outputs."""
    weights = ICP_CONFIG['scoring_weights']
    reasons = []
    
    score = weights['base_score']
    reasons.append(f"Base score of {score} points.")

    if tool_results['industry_match']:
        score += weights['industry_match']
        reasons.append(f"+{weights['industry_match']} for matching industry.")
    else:
        reasons.append("+0 for non-target industry.")

    if tool_results['employee_count_match']:
        score += weights['employee_count_within_range']
        reasons.append(f"+{weights['employee_count_within_range']} for employee count in range.")
    else:
        reasons.append("+0 for employee count out of range.")

    if tool_results['location_match']:
        score += weights['location_match']
        reasons.append(f"+{weights['location_match']} for matching location.")
    else:
        reasons.append("+0 for non-target location.")

    if tool_results['job_title_match']:
        score += weights['job_title_match']
        reasons.append(f"+{weights['job_title_match']} for target job title.")
    else:
        reasons.append("+0 for non-target job title.")
        
    if tool_results['is_excluded_title']:
        score += weights['is_excluded_title']
        reasons.append(f"{weights['is_excluded_title']} for excluded job title.")

    score = max(0, min(100, score))

    # Determine final status
    status = "NEEDS_REVIEW"
    if tool_results['is_excluded_title']:
        status = "NOT_QUALIFIED"
        reasons.append("Final Status: NOT_QUALIFIED due to excluded title.")
    elif score < 30:
        status = "NOT_QUALIFIED"
        reasons.append("Final Status: NOT_QUALIFIED due to low score.")
    elif score >= 70: # Changed from 50 in your prompt to match other examples
        status = "QUALIFIED"
        reasons.append("Final Status: QUALIFIED due to high score.")
    else:
        reasons.append("Final Status: NEEDS_REVIEW due to score in the middle range.")

    reasoning_str = " ".join(reasons)
        
    return score, status, reasoning_str