"""Weld identical wireframe vertices without changing the source asset or loader."""
import copy


def compact_scene(source):
    scene = copy.deepcopy(source)
    for primitives in scene.meshes:
        for mesh in primitives:
            lookup, remap, vertices, joints, weights = {}, [], [], [], []
            for index in range(len(mesh.vertices) // 8):
                vertex = mesh.vertices[index*8:index*8+8]
                joint = tuple(mesh.joints[index]) if mesh.joints else ()
                weight = tuple(mesh.weights[index]) if mesh.weights else ()
                # Normals/UVs are not used by either wireframe renderer. Skin
                # weights are part of identity, so animated seams stay correct.
                key = (tuple(vertex[:3]), joint, weight)
                if key not in lookup:
                    lookup[key] = len(lookup)
                    vertices.extend(vertex)
                    if mesh.joints:
                        joints.append(joint)
                    if mesh.weights:
                        weights.append(weight)
                remap.append(lookup[key])
            mesh.indices = [remap[i] for i in (mesh.indices or range(len(remap)))]
            mesh.vertices, mesh.joints, mesh.weights = vertices, joints, weights
            mesh._edges = None
    return scene
