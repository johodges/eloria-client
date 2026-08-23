#include <cal3d/cal3d.h>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

int main(int argc, char **argv)
{
	if (argc != 2)
	{
		std::cerr << "usage: validate_cal3d_runtime DATA_ROOT\n";
		return 2;
	}
	const std::string root = argv[1];
	CalCoreModel model("Eloria generated humanoid validation");
	if (!model.loadCoreSkeleton(root + "/actors/eloria_humanoid.csf"))
	{
		std::cerr << "skeleton: " << CalError::getLastErrorDescription() << '\n';
		return 1;
	}
	std::vector<int> mesh_ids;
	for (const char *mesh: { "eloria_shirt.cmf", "eloria_legs.cmf",
		"eloria_boots.cmf", "eloria_head_0.cmf" })
	{
		const int mesh_id = model.loadCoreMesh(root + "/actors/" + mesh);
		if (mesh_id < 0)
		{
			std::cerr << mesh << ": " << CalError::getLastErrorDescription() << '\n';
			return 1;
		}
		mesh_ids.push_back(mesh_id);
	}
	for (const char *animation: { "idle.caf", "walk.caf", "run.caf",
		"attack.caf", "pain.caf", "die.caf", "harvest.caf", "sit.caf" })
	{
		if (model.loadCoreAnimation(root + "/animations/eloria/" + animation) < 0)
		{
			std::cerr << animation << ": "
				<< CalError::getLastErrorDescription() << '\n';
			return 1;
		}
	}
	CalModel instance(&model);
	for (int mesh_id: mesh_ids)
		if (!instance.attachMesh(mesh_id)) return 1;
	instance.update(0.0f);
	CalRenderer *renderer = instance.getRenderer();
	if (!renderer->beginRendering() || renderer->getMeshCount() != 4)
	{
		std::cerr << "generated binary model produced no renderable meshes\n";
		return 1;
	}
	int vertices = 0, faces = 0;
	float minimum[3] = { std::numeric_limits<float>::max(),
		std::numeric_limits<float>::max(), std::numeric_limits<float>::max() };
	float maximum[3] = { std::numeric_limits<float>::lowest(),
		std::numeric_limits<float>::lowest(), std::numeric_limits<float>::lowest() };
	for (int mesh = 0; mesh < renderer->getMeshCount(); ++mesh)
	{
		for (int submesh = 0; submesh < renderer->getSubmeshCount(mesh); ++submesh)
		{
			if (!renderer->selectMeshSubmesh(mesh, submesh)) return 1;
			const int vertex_count = renderer->getVertexCount();
			std::vector<float> positions(vertex_count * 3);
			if (renderer->getVertices(positions.data()) != vertex_count)
			{
				std::cerr << "could not obtain transformed vertices\n";
				return 1;
			}
			for (int vertex = 0; vertex < vertex_count; ++vertex)
				for (int axis = 0; axis < 3; ++axis)
				{
					const float value = positions[vertex * 3 + axis];
					if (!std::isfinite(value))
					{
						std::cerr << "generated model has a non-finite vertex\n";
						return 1;
					}
					if (value < minimum[axis]) minimum[axis] = value;
					if (value > maximum[axis]) maximum[axis] = value;
				}
			vertices += vertex_count;
			faces += renderer->getFaceCount();
		}
	}
	renderer->endRendering();
	if (vertices != 288 || faces != 144)
	{
		std::cerr << "unexpected generated geometry: vertices=" << vertices
			<< " faces=" << faces << '\n';
		return 1;
	}
	if (minimum[0] > -0.3f || maximum[0] < 0.3f || minimum[2] > -0.02f
		|| maximum[2] < 1.6f || minimum[0] < -0.5f || maximum[0] > 0.5f
		|| maximum[2] > 1.8f)
	{
		std::cerr << "unexpected transformed bounds: [" << minimum[0] << ','
			<< minimum[1] << ',' << minimum[2] << "] - [" << maximum[0]
			<< ',' << maximum[1] << ',' << maximum[2] << "]\n";
		return 1;
	}
	std::cout << "Generated binary Cal3D humanoid loaded with " << vertices
		<< " vertices and " << faces << " faces; transformed bounds ["
		<< minimum[0] << ',' << minimum[1] << ',' << minimum[2] << "] - ["
		<< maximum[0] << ',' << maximum[1] << ',' << maximum[2] << "]\n";
	return 0;
}
