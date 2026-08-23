#include <cal3d/cal3d.h>
#include <cmath>
#include <iostream>
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
	for (int mesh = 0; mesh < renderer->getMeshCount(); ++mesh)
	{
		for (int submesh = 0; submesh < renderer->getSubmeshCount(mesh); ++submesh)
		{
			if (!renderer->selectMeshSubmesh(mesh, submesh)) return 1;
			vertices += renderer->getVertexCount();
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
	std::cout << "Generated binary Cal3D humanoid loaded with " << vertices
		<< " vertices and " << faces << " faces\n";
	return 0;
}
