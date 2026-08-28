# Offline preview rasteriser. Not part of the runtime package - it exists only
# so the region can be looked at while it is being authored.
CFLAGS ?= -O3 -ffast-math -shared -fPIC

libraster.so: raster.c
	$(CC) $(CFLAGS) -o $@ $< -lm

clean:
	rm -f libraster.so

.PHONY: clean
