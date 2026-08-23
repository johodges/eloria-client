#include <cal3d/cal3d.h>
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
	if (model.loadCoreSkeleton(root + "/actors/eloria_humanoid.xsf") < 0)
	{
		std::cerr << "skeleton: " << CalError::getLastErrorDescription() << '\n';
		return 1;
	}
	for (const char *mesh: { "eloria_shirt.xmf", "eloria_legs.xmf",
		"eloria_boots.xmf", "eloria_head_0.xmf" })
	{
		if (model.loadCoreMesh(root + "/actors/" + mesh) < 0)
		{
			std::cerr << mesh << ": " << CalError::getLastErrorDescription() << '\n';
			return 1;
		}
	}
	for (const char *animation: { "idle.xaf", "walk.xaf", "run.xaf",
		"attack.xaf", "pain.xaf", "die.xaf", "harvest.xaf", "sit.xaf" })
	{
		if (model.loadCoreAnimation(root + "/animations/eloria/" + animation) < 0)
		{
			std::cerr << animation << ": "
				<< CalError::getLastErrorDescription() << '\n';
			return 1;
		}
	}
	std::cout << "Generated Cal3D humanoid loaded successfully\n";
	return 0;
}
