
#include "cal3d_io_wrapper.h"
#include "../elc_private.h"
#include "../errors.h"
#include <cal3d/global.h>
#include <cal3d/cal3d.h>
#include "cal3d/coretrack.h"
#include <iostream>
#include <vector>
#include "elfilewrapper.h"

//****************************************************************************//
// CalLoader wrapper functions definition                                     //
//****************************************************************************//

class ElDataSource: public CalDataSource
{
	private:
		el_file_ptr m_file;

	public:
		ElDataSource(const std::string &file_name)
		{
			m_file = el_open(file_name.c_str());
		}

		virtual ~ElDataSource()
		{
			el_close(m_file);
		}

		virtual bool ok() const
		{
			return m_file != 0;
		}

		virtual void setError() const
		{
		}

		virtual bool readBytes(void* pBuffer, int length)
		{
			return el_read(m_file, length, pBuffer) == length;
		}

		virtual bool readShort(short& value)
		{
			Sint16 tmp;
			int length;

			length = el_read(m_file, sizeof(Sint16), &tmp);

			value = SDL_SwapLE16(tmp);

			return length == sizeof(Sint16);
		}

		virtual bool readFloat(float &value)
		{
#ifdef FASTER_STARTUP
			return el_read_float(m_file, &value);
#else
			float tmp;
			int length;

			length = el_read(m_file, sizeof(float), &tmp);

			value = SwapLEFloat(tmp);

			return length == sizeof(float);
#endif
		}

		virtual bool readInteger(int &value)
		{
#ifdef FASTER_STARTUP
			return el_read_int(m_file, &value);
#else
			Sint32 tmp;
			int length;

			length = el_read(m_file, sizeof(Sint32), &tmp);

			value = SDL_SwapLE32(tmp);

			return length == sizeof(Sint32);
#endif
		}

		virtual bool readString(std::string &strValue)
		{
			char* str;
			int length;

			if (readInteger(length))
			{
				if (length >= 0)
				{

					str = new char[length];

					el_read(m_file, length, str);

					strValue = str;

					delete [] str;

					return true;
				}
				else
				{
					return false;
				}
			}
			else
			{
				return false;
			}
		}

};

/*
 * CalLoader's CalDataSource overloads parse only the binary CSF/CAF/CMF/CRF
 * formats.  The filename and memory-buffer overloads also detect Cal3D XML,
 * but the filename overload cannot use EL's zip/custom-path filesystem.  Read
 * XML through that filesystem, then give Cal3D a nul-terminated memory buffer.
 */
static std::vector<char> read_cal3d_xml(const std::string &file_name)
{
	el_file_ptr file = el_open(file_name.c_str());
	std::vector<char> data;
	if (!file)
		return data;
	const Sint64 size = el_get_size(file);
	if (size > 0)
	{
		data.resize(static_cast<size_t>(size) + 1, '\0');
		if (el_read(file, size, data.data()) != size)
			data.clear();
	}
	el_close(file);
	if (data.size() < 8 || memcmp(data.data(), "<HEADER", 7) != 0)
		data.clear();
	return data;
}

static CalCoreAnimationPtr load_core_animation(const std::string &file_name)
{
	std::vector<char> xml = read_cal3d_xml(file_name);
	if (!xml.empty())
		return CalLoader::loadCoreAnimation(xml.data(), 0);
	ElDataSource file(file_name);
	return CalLoader::loadCoreAnimation(file, 0);
}

static CalCoreMaterialPtr load_core_material(const std::string &file_name)
{
	std::vector<char> xml = read_cal3d_xml(file_name);
	if (!xml.empty())
		return CalLoader::loadCoreMaterial(xml.data());
	ElDataSource file(file_name);
	return CalLoader::loadCoreMaterial(file);
}

static CalCoreMeshPtr load_core_mesh(const std::string &file_name)
{
	std::vector<char> xml = read_cal3d_xml(file_name);
	if (!xml.empty())
		return CalLoader::loadCoreMesh(xml.data());
	ElDataSource file(file_name);
	return CalLoader::loadCoreMesh(file);
}

static CalCoreSkeletonPtr load_core_skeleton(const std::string &file_name)
{
	std::vector<char> xml = read_cal3d_xml(file_name);
	if (!xml.empty())
		return CalLoader::loadCoreSkeleton(xml.data());
	ElDataSource file(file_name);
	return CalLoader::loadCoreSkeleton(file);
}

class CalAnimationCache
{
	private:
		typedef std::pair<std::string,float> AnimationKey;
		typedef std::map<AnimationKey, CalCoreAnimationPtr> AnimationsMap;
		
		AnimationsMap m_animations;

		CalAnimationCache()
		{
		}


		//The m_animations map will free itself when the CalAnimationCache singleton goes out of 
		//scope. However, for some reason the tracks/keyframes of that animation are not managed with
		//reference-counted objects (like everything else in Cal3D). So, we have to explicitly delete them.
		//At that point, it's probably best not to leave stale animation objects in the map, so we remove them as well.
		~CalAnimationCache()
		{
			while (!m_animations.empty()) {
				free_and_remove_animation(m_animations.begin());
			}
		}

		//This function should work externally, too, although we never delete items from the animations cache.
		void free_and_remove_animation(const AnimationsMap::iterator& animIt) {
			//Remove all keyframes (via destroy()) from each track individually.
			std::list<CalCoreTrack*>& trackList = animIt->second->getListCoreTrack();
			for (auto track: trackList)
			{
				track->destroy();
				delete track;
			}

			//Clear the track list too.
			trackList.clear();

			//Now eject this item from the map.
			m_animations.erase(animIt);
		}
		
		static CalAnimationCache & instance()
		{
			static CalAnimationCache cache;

			return cache;
		}
		
	public:
		
		static CalCoreAnimationPtr loadAnimation(const std::string &fileName, float scale)
		{
			AnimationsMap &anims = instance().m_animations;
			AnimationKey key(fileName, scale);
			AnimationsMap::iterator it = anims.find(key);

			if (it != anims.end())
			{
				return it->second;
			}
			else
			{
				CalCoreAnimationPtr anim_ptr = load_core_animation(fileName);

				if (anim_ptr)
				{
					CalCoreAnimation_Scale(anim_ptr.get(), scale);
					anim_ptr->setFilename(fileName);
				}
				
				anims[key] = anim_ptr;

				return anim_ptr;
			}
		}
		
};

extern "C" CalCoreAnimation *CalLoader_ELLoadCoreAnimation(CalLoader *self,
	const char *strFilename)
{
	assert(self);

	CalCoreAnimation *core_animation = explicitIncRef(load_core_animation(strFilename).get());

	if (core_animation)
	{
		core_animation->setFilename(strFilename);
	}
			
	return core_animation;
}

extern "C" CalCoreMaterial *CalLoader_ELLoadCoreMaterial(CalLoader *self, const char *strFilename)
{
	assert(self);

	CalCoreMaterial *core_material = explicitIncRef(load_core_material(strFilename).get());

	if (core_material)
	{
		core_material->setFilename(strFilename);
	}
			
	return core_material;
}

extern "C" CalCoreMesh *CalLoader_ELLoadCoreMesh(CalLoader *self, const char *strFilename)
{
	assert(self);

	CalCoreMesh *core_mesh = explicitIncRef(load_core_mesh(strFilename).get());

	if (core_mesh)
	{
		core_mesh->setFilename(strFilename);
	}
			
	return core_mesh;
}

extern "C" CalCoreSkeleton *CalLoader_ELLoadCoreSkeleton(CalLoader *self, const char *strFilename)
{
	assert(self);

	return explicitIncRef(load_core_skeleton(strFilename).get());
}

extern "C" int CalCoreModel_ELLoadCoreAnimation(CalCoreModel *self, const char *strFilename, float scale)
{
	assert(self);

	CalCoreAnimationPtr core_animation = CalAnimationCache::loadAnimation(strFilename, scale);

	if (!core_animation)
	{
		return -1;
	}

	return self->addCoreAnimation(core_animation.get());
}

extern "C" int CalCoreModel_ELLoadCoreMaterial(CalCoreModel *self, const char *strFilename)
{
	assert(self);

	CalCoreMaterialPtr core_material = load_core_material(strFilename);

	if (!core_material)
	{
		return -1;
	}
	else
	{
		core_material->setFilename(strFilename);
	}

	return self->addCoreMaterial(core_material.get());
}

extern "C" int CalCoreModel_ELLoadCoreMesh(CalCoreModel *self, const char *strFilename)
{
	assert(self);

	CalCoreMeshPtr core_mesh = load_core_mesh(strFilename);

	if (!core_mesh)
	{
		return -1;
	}
	else
	{
		core_mesh->setFilename(strFilename);
	}

	return self->addCoreMesh(core_mesh.get());
}

extern "C" CalBoolean CalCoreModel_ELLoadCoreSkeleton(CalCoreModel *self, const char *strFilename)
{
	assert(self);

	CalCoreSkeletonPtr core_skeleton = load_core_skeleton(strFilename);

	if (!core_skeleton)
	{
		return False;
	}

	self->setCoreSkeleton(core_skeleton.get());

	return True;
}

extern "C" void set_invert_v_coord()
{
	CalLoader::setLoadingMode(LOADER_INVERT_V_COORD);
}

