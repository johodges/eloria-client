"""A smooth cranial fitting surface that leaves horns and crystals exposed."""
import numpy as np
import trimesh
from scipy.optimize import least_squares
from integrate_luminous_sources import source_head
from verify_shared_player_bodies import primitives


def allows_protrusions(slug):
    return slug.startswith(('votary_', 'stoneborn_')) or slug == 'glasswarden_male'


def hair_skull(document, binary, slug):
    head = source_head(document, binary)
    if not allows_protrusions(slug):
        return head
    skull, weights, matrix = head
    v = np.asarray(skull.vertices)
    # Fit the skull below the horn/crest roots, excluding nose and outer ears.
    samples = v[(v[:,1] > .025) & (v[:,1] < .115) & (abs(v[:,0]) < .087) & (v[:,2] < .07)]
    samples = samples[::max(1, len(samples)//2500)]
    def residual(parameters):
        centre = np.array([0., parameters[0], parameters[1]])
        return (np.linalg.norm((samples-centre)/parameters[2:], axis=1)-1)*.09
    fit = least_squares(residual, [.065,-.010,.083,.10,.083],
                        bounds=([.035,-.035,.060,.070,.060],[.100,.035,.115,.135,.125]),
                        loss='soft_l1',f_scale=.002)
    centre=np.array([0.,fit.x[0],fit.x[1]])
    eyes=np.concatenate([a['POSITION'][np.unique(f)] for name,_,a,f in primitives(document,binary) if name=='eyes'])
    eye_height=np.median(((eyes-matrix[:3,3])@matrix[:3,:3])[:,1])
    # Crest roots can resemble a tall cylinder. Eye level provides an
    # anatomical ceiling for the inferred cranium beneath those protrusions.
    fit.x[3]=min(fit.x[3],max(.07,eye_height+.10-centre[1]))
    proxy=trimesh.creation.icosphere(subdivisions=3)
    proxy.vertices=np.asarray(proxy.vertices)*fit.x[2:]+centre
    # The retained source head is rigidly bound; the proxy follows that joint.
    weight=np.zeros((len(proxy.vertices),weights.shape[1]))
    weight[:,int(np.argmax(weights.sum(0)))]=1.
    return proxy,weight,matrix
