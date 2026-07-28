import sys
sys.path.insert(0, '/Users/haimptasznik/Desktop/haimos-transmission-rights-repo/scripts')
from validate_phase1a_regional_calendar import run_validation

res = run_validation()

print('final_gate_status=', res.get('final_gate_status'))
print('failure_count=', len(res.get('failures', [])))
print('readiness_for_full_79_month_integration=', res.get('readiness_for_full_79_month_integration'))
print('dst_transitions=', res.get('dst_validation', {}).get('dst_transitions', {}))
print('qld_remaining_non_dst=', res.get('dst_validation', {}).get('qld_remaining_non_dst'))
print('failures=')
for failure in res.get('failures', []):
    print(failure)
