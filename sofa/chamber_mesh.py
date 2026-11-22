"""Generate an illustrative hollow, tetrahedral pneumatic chamber in SI units.

This rectangular test specimen is not reconstructed from the exosuit photos.
"""
from collections import defaultdict


def signed_volume(a,b,c,d):
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)];w=[d[i]-a[i] for i in range(3)]
    return (u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0]))/6


def generate_chamber(nx=16,ny=8,nz=6,length=.20,width=.048,height=.036):
    if min(nx,ny,nz)<3 or min(length,width,height)<=0:
        raise ValueError("At least three cells per axis and positive dimensions are required")
    def index(i,j,k):return (i*(ny+1)+j)*(nz+1)+k
    all_points=[[length*i/nx,width*(j/ny-.5),height*(k/nz-.5)]
                for i in range(nx+1) for j in range(ny+1) for k in range(nz+1)]
    tets=[]
    split=[(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6),(0,5,1,6)]
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if not (i in (0,nx-1) or j in (0,ny-1) or k in (0,nz-1)):continue
                ids=[index(i,j,k),index(i+1,j,k),index(i+1,j+1,k),index(i,j+1,k),
                     index(i,j,k+1),index(i+1,j,k+1),index(i+1,j+1,k+1),index(i,j+1,k+1)]
                for pattern in split:
                    tet=[ids[a] for a in pattern]
                    if signed_volume(*(all_points[a] for a in tet))<0:tet[1],tet[2]=tet[2],tet[1]
                    tets.append(tet)
    used=sorted({i for t in tets for i in t});mapping={old:new for new,old in enumerate(used)}
    points=[all_points[i] for i in used];tets=[[mapping[i] for i in t] for t in tets]
    count=defaultdict(list)
    for a,b,c,d in tets:
        for f in ((a,c,b),(a,b,d),(a,d,c),(b,c,d)):count[tuple(sorted(f))].append(f)
    boundary=[list(faces[0]) for faces in count.values() if len(faces)==1]
    def on_outer_face(face):
        for axis,limits in enumerate(((0,length),(-width/2,width/2),(-height/2,height/2))):
            if any(all(abs(points[i][axis]-limit)<1e-10 for i in face) for limit in limits):return True
        return False
    outer=[face for face in boundary if on_outer_face(face)]
    # Boundary triangles point out of the solid. Reverse the internal surface
    # to point out of the gas volume, so positive pressure expands the cavity.
    inner=[[f[0],f[2],f[1]] for f in boundary if not on_outer_face(f)]
    inner_ids=sorted({i for f in inner for i in f});inner_map={old:new for new,old in enumerate(inner_ids)}
    cavity_points=[points[i] for i in inner_ids]
    cavity_triangles=[[inner_map[i] for i in f] for f in inner]
    fixed=[i for i,p in enumerate(points) if abs(p[0])<1e-10]
    # A stiff bottom layer gives the illustrative specimen a bending bias.
    young=[30e6 if sum(points[i][2] for i in t)/4 < -height/2+height/nz+1e-10 else 2e6 for t in tets]
    return {"positions":points,"tetrahedra":tets,"outer_triangles":outer,
            "cavity_positions":cavity_points,"cavity_triangles":cavity_triangles,
            "fixed_indices":fixed,"young_modulus_pa":young,
            "dimensions_m":[length,width,height],
            "wall_m":[length/nx,width/ny,height/nz],
            "cavity_volume_m3":(length-2*length/nx)*(width-2*width/ny)*(height-2*height/nz)}
