import json
import pytest
from contractlens import config
from contractlens.engine import budget_context, Investigator, BudgetExceeded


def test_defaults_and_override(monkeypatch):
    b = config.run_budget()
    assert (b.model_calls,b.tool_calls,b.timeout_seconds)==(24,40,300)
    monkeypatch.setenv('CONTRACTLENS_BUDGET_MODEL_CALLS','32')
    assert config.run_budget().model_calls==32

@pytest.mark.parametrize('name,value', [('MODEL_CALLS','0'),('TOOL_CALLS','unlimited'),('OUTPUT_TOKENS','90000'),('EVIDENCE_EVENTS','32')])
def test_invalid_configuration_fails(monkeypatch,name,value):
    monkeypatch.setenv('CONTRACTLENS_BUDGET_'+name,value)
    with pytest.raises(ValueError):config.run_budget()


def test_budget_context_preserves_tool_pairing_and_history():
    history=[{'role':'user','content':[{'type':'tool_result','tool_use_id':'t1','content':'data'}]}]
    result=budget_context(history,config.run_budget(),22,37)
    assert result[0]['content'][0]==history[0]['content'][0]
    assert len(history[0]['content'])==1
    notice=json.loads(result[0]['content'][-1]['text'])['run_budget']
    assert notice['model_calls_remaining_including_this']==3
    assert notice['tool_calls_remaining']==3
    assert 'Reporting phase' in notice['instruction']


def test_tool_calls_can_exceed_old_limit_but_stop_at_configured_limit(monkeypatch):
    monkeypatch.setenv('CONTRACTLENS_BUDGET_TOOL_CALLS','16')
    obj=Investigator('test',{'package_id':'fictional','checklist':[]},emit=lambda *a:None)
    obj.coverage=lambda:{}
    obj.plans=[{}]
    for _ in range(16):obj.invoke('check_evidence_coverage',{})
    with pytest.raises(BudgetExceeded):obj.invoke('check_evidence_coverage',{})
