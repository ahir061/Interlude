import json
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from interlude.config import Settings
from interlude.db import Base, VideoRow, JobRow, ArtifactRow
from interlude.domain import BrandExplanation
from interlude.main import create_app
from interlude.providers.base import ProviderError


def test_explanation_only_describes_selected_brand_and_cannot_change_decision(tmp_path, monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    video,job=str(uuid4()),str(uuid4())
    path=tmp_path/'debug.json'
    data={'decisions':[{'candidate_id':'selected','accepted':True,'selected_brand_id':'brand_a',
          'semantics':{'dominant_activity':'cooking','evidence':[]},
          'debug':{'brands':[],'brand_safety_verification':[{'brand_id':'brand_a','verdict':'SAFE'}]}},
          {'candidate_id':'rejected','accepted':False}]}
    path.write_text(json.dumps(data))
    with factory.begin() as s:
        s.add(VideoRow(id=video,path='unused',metadata_json={}));s.flush()
        s.add(JobRow(id=job,video_id=video,status='COMPLETED'));s.flush()
        s.add(ArtifactRow(job_id=job,kind='debug',path=str(path)))
    monkeypatch.setattr('interlude.main.sessions',lambda _:factory)
    calls=[]
    def explain(self,payload):
        calls.append(payload)
        return BrandExplanation(summary='Cooking matches the food category.',confidence=0.9)
    monkeypatch.setattr('interlude.providers.perception.PerceptionClient.explain_selection',explain)
    with TestClient(create_app(Settings(_env_file=None,data_dir=tmp_path))) as c:
        route=f'/api/videos/{video}/candidates/'
        assert c.post(route+'rejected/explanation').status_code==404
        assert not calls
        result=c.post(route+'selected/explanation')
        assert result.status_code==200 and result.json()['source']=='Qwen'
        assert calls[0]['brand']['brand_id']=='brand_a'
        assert json.loads(path.read_text())==data
        def unavailable(*args):
            raise ProviderError('semantic_timeout')
        monkeypatch.setattr('interlude.providers.perception.PerceptionClient.explain_selection',unavailable)
        assert c.post(route+'selected/explanation').status_code==503
        assert json.loads(path.read_text())==data
