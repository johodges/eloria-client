"""Build and verify the shared body set from approved canonical source GLBs.

Outputs are scratch candidates. Both templates receive the same continuous neck construction.
Use --library to replay complete locomotion cycles as part of this build.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,os
from pathlib import Path
import sys

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(key,'1')
import shared_player_bodies as body
import verify_shared_player_bodies as check

RACES={f'{race}_{gender}' for race in ('luminous','votary','glasswarden','orun','greyhaven','ssarathi','stoneborn','mycelari') for gender in ('male','female')}


def build_one(source_dir,out,slug,code_hash,library):
    source=source_dir/(slug+'.glb');template=source_dir/('luminous_'+slug.rsplit('_',1)[1]+'.glb')
    target=out/'bodies'/source.name;target.parent.mkdir(parents=True,exist_ok=True)
    if body.digest(body.__file__)!=code_hash:raise ValueError('Body generator changed')
    body.run(source,template,target)
    geometry=check.verify(target,source,template)
    if geometry['errors']:raise ValueError((slug,geometry['errors']))
    record={'slug':slug,'geometry':geometry}
    if library:
        sys.path.insert(0,str(Path(__file__).parent/'tpose_bodies'))
        import verify as motion
        record['motion']=motion.verify(target,library,source,['Idle_Subtle','Walk','Jog','Run_Female','Fighting_Idle'])
        if record['motion']['errors']:raise ValueError((slug,record['motion']['errors']))
    if body.digest(body.__file__)!=code_hash:raise ValueError('Body generator changed')
    report=out/'reports'/(slug+'.json');report.parent.mkdir(parents=True,exist_ok=True)
    if report.exists():raise FileExistsError(report)
    report.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


def build(source_dir,out,jobs,library=None):
    if out.exists():raise FileExistsError('Use a new scratch directory')
    if 'godot-client' in out.resolve().parts:raise ValueError('Never export over client assets')
    if {p.stem for p in source_dir.glob('*.glb')}!=RACES:raise ValueError('Expected all 16 canonical source bodies')
    source_hashes={s:body.digest(source_dir/(s+'.glb')) for s in RACES}
    code=body.digest(body.__file__);records=[]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures=[pool.submit(build_one,source_dir,out,s,code,library) for s in sorted(RACES)]
        for f in as_completed(futures):
            record=f.result();records.append(record);print(record['slug'],'verified',flush=True)
    if source_hashes!={s:body.digest(source_dir/(s+'.glb')) for s in RACES}:raise ValueError('Source set changed')
    result={'sourceSHA256':source_hashes,'generatorSHA256':code,'driverSHA256':body.digest(__file__),
            'candidates':{r['slug']:r['geometry']['candidateSHA256'] for r in records},'motionReplayed':library is not None}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--jobs',type=int,choices=range(1,9),default=3)
    ap.add_argument('--library',type=Path)
    args=ap.parse_args();build(args.sources,args.out,args.jobs,args.library)
