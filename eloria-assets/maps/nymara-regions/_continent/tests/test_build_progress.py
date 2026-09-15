"""Build progress and composition freshness, the two records an editor reads.

Neither may ever stop a build: progress warns on an unwritable path and the
freshness report answers with the same digests the stages refuse to work
without, including digests a sibling branch recorded that this one cannot map.
"""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import build_continent as B
import build_progress as P


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ProgressRecordTests(unittest.TestCase):
    def test_a_stage_records_the_documented_shape_and_clamps_its_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'generated/progress.json';progress=P.Progress(path)
            progress.start('compose',4)
            record=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(tuple(record),P.KEYS)
            self.assertEqual(record['stage'],'compose');self.assertEqual(record['step'],'')
            self.assertEqual(record['fraction'],0);self.assertEqual(record['status'],'running')
            self.assertIsNone(record['exit']);self.assertEqual(record['pid'],os.getpid())
            self.assertTrue(record['startedAt'].endswith('Z'),record['startedAt'])
            self.assertGreaterEqual(record['updatedAt'],record['startedAt'])
            progress.step('roads and routing',1,4)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['fraction'],.25)
            progress.step('counted against the stage total')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['fraction'],.5)
            for done,total,expected in ((9,4,1),(-3,4,0),(1,0,0)):
                progress.step('clamped',done,total)
                current=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(current['fraction'],expected,(done,total))
                self.assertEqual(current['step'],'clamped');self.assertEqual(current['status'],'running')
            progress.start('a stage with no inner steps');progress.step('unknown total',1)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['fraction'],0)
            # A replaced record is the only file left: readers never see a partial write.
            self.assertEqual([p.name for p in path.parent.iterdir()],['progress.json'])

    def test_finishing_records_the_exit_code_and_its_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'progress.json';progress=P.Progress(path)
            progress.start('geometry',12);progress.step('whitehorn_range',3,12)
            progress.finish(3)
            failed=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(failed['status'],'failed');self.assertEqual(failed['exit'],3)
            self.assertEqual(failed['fraction'],.25);self.assertEqual(failed['step'],'whitehorn_range')
            started=failed['startedAt']
            progress.finish(0)
            done=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(done['status'],'done');self.assertEqual(done['exit'],0)
            self.assertEqual(done['fraction'],1);self.assertEqual(done['startedAt'],started)
            self.assertIn(done['status'],P.STATUSES)

    def test_a_failed_build_is_recorded_by_the_installed_exception_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'progress.json';progress=P.Progress(path);chained=[]
            hook=sys.excepthook
            try:
                sys.excepthook=lambda *arguments:chained.append(arguments)
                progress.watch();progress.start('publish')
                sys.excepthook(subprocess.CalledProcessError,subprocess.CalledProcessError(7,'publish'),None)
            finally:sys.excepthook=hook
            self.assertEqual(len(chained),1,'the previous exception hook must still run')
            record=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(record['status'],'failed');self.assertEqual(record['exit'],7)
            self.assertEqual(record['stage'],'publish')

    def test_an_unwritable_record_warns_instead_of_stopping_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked=Path(tmp)/'progress.json';blocked.mkdir()
            progress=P.Progress(blocked);output=io.StringIO()
            with redirect_stdout(output):
                progress.start('compose',4);progress.step('roads and routing',1,4);progress.finish(1)
            self.assertEqual(output.getvalue().count('Warning: build progress not written'),3)
            self.assertTrue(blocked.is_dir())
            # The temporary files it could not move into place are cleaned up.
            self.assertEqual(list(Path(tmp).iterdir()),[blocked])

    def test_an_inert_record_writes_nothing_and_says_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress=P.Progress(None);output=io.StringIO()
            with redirect_stdout(output):
                progress.start('compose',4);progress.step('roads',1,4);progress.finish(0)
            self.assertEqual(output.getvalue(),'')
            self.assertEqual(list(Path(tmp).iterdir()),[])
            path=Path(tmp)/'progress.json'
            progress.attach(path).finish(0)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['status'],'done')


class CompositionFreshnessTests(unittest.TestCase):
    def fixture(self,root):
        """The records prepare() writes, for a client tree of fixture sources."""
        client=root/'client';continent=client/'eloria-assets/maps/nymara-regions/_continent'
        generated=continent/'generated';generated.mkdir(parents=True)
        plan=continent/'diagonal-plan.json';plan.write_text('{"regions": []}\n',encoding='utf-8')
        sources={}
        for name in B.SHAPING_SOURCES:
            source=continent/name;source.write_text(f'# fixture {name}\n',encoding='utf-8')
            sources[str(source.relative_to(client))]=digest(source)
        builder=continent/'build_continent.py';builder.write_text('# fixture builder\n',encoding='utf-8')
        sources[str(builder.relative_to(client))]=digest(builder)
        profile=continent/'legacy-server-profile/config/eloria/maps.txt'
        profile.parent.mkdir(parents=True);profile.write_text('# fixture entrances\n',encoding='utf-8')
        self.write(generated/'composition.json',{'schema':1,'planSha256':digest(plan),
            'entranceProfileSha256':digest(profile),'compositionAlgorithmSha256':B.composition_algorithm_sha(),
            'library':{},'sources':sources,'objects':3,'roads':7})
        return client,continent,generated

    def write(self,path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

    def freshness(self,client,continent,generated):
        with patch.object(B,'HERE',continent),patch.object(B,'CLIENT',client):
            return B.composition_freshness(generated)

    def test_an_untouched_composition_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,continent,generated=self.fixture(Path(tmp))
            state=self.freshness(client,continent,generated)
            self.assertTrue(state['fresh'],state);self.assertTrue(state['composed'])
            self.assertEqual((state['changed'],state['missing'],state['unknown']),([],[],[]))
            self.assertEqual(state['recorded'],state['current'])
            self.assertEqual(state['recorded']['plan'],digest(continent/'diagonal-plan.json'))
            self.assertIn('eloria-assets/maps/nymara-regions/_continent/landscape.py',state['recorded'])
            # Sources the composition records but the stages do not gate on stay out of it.
            self.assertNotIn('eloria-assets/maps/nymara-regions/_continent/build_continent.py',state['recorded'])

    def test_an_edited_plan_or_shaping_source_reads_as_stale(self):
        for name,expected in (('diagonal-plan.json','plan'),
                              ('content.py','eloria-assets/maps/nymara-regions/_continent/content.py'),
                              ('legacy-server-profile/config/eloria/maps.txt','entranceProfile')):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                client,continent,generated=self.fixture(Path(tmp))
                (continent/name).write_text('# edited by the plan editor\n',encoding='utf-8')
                state=self.freshness(client,continent,generated)
                self.assertFalse(state['fresh'])
                self.assertEqual(state['changed'],[expected],state['changed'])
                self.assertEqual(state['missing'],[])
                self.assertNotEqual(state['recorded'][expected],state['current'][expected])

    def test_a_deleted_input_is_missing_rather_than_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,continent,generated=self.fixture(Path(tmp))
            (continent/'hull_settle.py').unlink()
            composition=json.loads((generated/'composition.json').read_text(encoding='utf-8'))
            composition['objectEditsSha256']='4'*64
            self.write(generated/'composition.json',composition)
            state=self.freshness(client,continent,generated)
            self.assertFalse(state['fresh'])
            self.assertEqual(sorted(state['missing']),
                ['eloria-assets/maps/nymara-regions/_continent/hull_settle.py','objectEdits'])
            self.assertEqual(state['changed'],[])
            self.assertIsNone(state['current']['objectEdits'])

    def test_a_recorded_digest_from_another_branch_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,continent,generated=self.fixture(Path(tmp))
            composition=json.loads((generated/'composition.json').read_text(encoding='utf-8'))
            composition['tideTableSha256']='9'*64
            composition['objectEditsSha256']=digest(continent/'diagonal-plan.json')
            self.write(generated/'composition.json',composition)
            (continent/'continent-edits.json').write_bytes((continent/'diagonal-plan.json').read_bytes())
            state=self.freshness(client,continent,generated)
            self.assertEqual(state['unknown'],['tideTableSha256'])
            self.assertEqual(state['recorded']['tideTableSha256'],'9'*64)
            self.assertEqual(state['changed'],[]);self.assertEqual(state['missing'],[])
            # An optional input this branch does know is checked like any other.
            self.assertEqual(state['recorded']['objectEdits'],state['current']['objectEdits'])
            self.assertFalse(state['fresh'])

    def test_an_uncomposed_output_reports_nothing_composed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=B.composition_freshness(Path(tmp))
            self.assertEqual(state,{'fresh':False,'composed':False,'changed':[],'missing':[],
                                    'unknown':[],'recorded':{},'current':{}})

    def test_the_switch_reports_without_a_library_and_exits_by_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            done=subprocess.run([sys.executable,str(HERE/'build_continent.py'),'--freshness','--output',tmp],
                                capture_output=True,text=True,cwd=str(HERE))
            self.assertEqual(done.returncode,2,done.stderr)
            self.assertFalse(json.loads(done.stdout)['composed'])
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__=='__main__':
    unittest.main()
