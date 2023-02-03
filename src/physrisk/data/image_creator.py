import io
from typing import Callable, List, MutableMapping, Optional

import numpy as np
import zarr.storage
from PIL import Image

from physrisk.data import colormap_provider
from physrisk.data.zarr_reader import ZarrReader


class ImageCreator:
    """Convert small arrays into images for map display.
    Intended for arrays <~1500x1500 (otherwise, recommended to use Mapbox tiles).
    """

    def __init__(self, store: Optional[MutableMapping] = None):
        self.reader = ZarrReader(store=store)

    def convert(
        self,
        path,
        format="PNG",
        colormap: str = "heating",
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> bytes:
        """Get image for path specified as array of bytes."""
        data = self.reader.all_data(path)
        if len(data.shape) == 3:
            data = data[:, :, :].squeeze(axis=0)
        if any(dim > 1500 for dim in data.shape):
            raise Exception("dimension too large (over 1500).")
        map_defn = colormap_provider.colormap(colormap)

        def get_colors(index: int):
            return map_defn[str(index)]

        rgba = self.to_rgba(data, get_colors, min_value=min_value, max_value=max_value)
        image = Image.fromarray(rgba, mode="RGBA")
        image_bytes = io.BytesIO()
        image.save(image_bytes, format=format)
        return image_bytes.getvalue()
        # final = image_bytes.read()
        # image.save("test_image.tiff", format='TIFF')

    def to_rgba(  # noqa: C901
        self,
        data: np.ndarray,
        get_colors: Callable[[int], List[int]],
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        nodata_lower: Optional[float] = None,
        nodata_upper: Optional[float] = None,
        nodata_bin_transparent: bool = False,
        min_bin_transparent: bool = False,
    ) -> np.ndarray:
        """Convert the data to an RGBA image using values provided by get_colors.
        We are particular about min and max values, ensuring that these get their own indices
        from the colormap. Thee rules are:
        0: value is nodata
        1: value <= min_value
        2: min_value < value < (max_value - min_value) / 253
        254: (max_value - min_value) / 253 <= value < max_value
        255 is >= max_value

        Args:
            data (np.ndarray): Two dimensional array.
            get_colors (Callable[[int], Tuple[int, int, int]]): When passed an integer index in range 0:256, returns RGB components as integers in range 0:256.
            min_value (Optional[float]): Minimum value. Defaults to None.
            max_value (Optional[float]): Maximum value. Defaults to None.
            nodata_lower (Optional[float], optional): If supplied, values smaller than or equal to nodata_lower threshold are considered nodata. Defaults to None.
            nodata_upper (Optional[float], optional): If supplied, values larger than or equal to nodata_upper threshold are considered nodata. Defaults to None.
            nodata_bin_transparent (bool, optional): If True make no_data bin transparent. Defaults to False.
            min_bin_transparent (bool, optional): If True make min_bin transparent. Defaults to False.

        Returns:
            np.ndarray: RGBA array.
        """  # noqa

        red = np.zeros(256, dtype=np.uint32)
        green = np.zeros(256, dtype=np.uint32)
        blue = np.zeros(256, dtype=np.uint32)
        a = np.zeros(256, dtype=np.uint32)
        for i in range(256):
            (red[i], green[i], blue[i], a[i]) = get_colors(i)
        if nodata_bin_transparent:
            a[0] = 0
        if min_bin_transparent:
            a[1] = 0
        mask_nodata = None
        if nodata_lower:
            mask_nodata = data <= nodata_lower
        if nodata_upper:
            mask_nodata = (mask_nodata | (data >= nodata_upper)) if mask_nodata is not None else (data >= nodata_upper)

        if min_value is None:
            min_value = data.min()
        if max_value is None:
            max_value = data.max()

        mask_ge_max = data >= max_value
        mask_le_min = data <= min_value

        np.add(data, -min_value, out=data)
        np.multiply(data, 253.0 / (max_value - min_value), out=data)
        np.add(data, 2.0, out=data)  # np.clip seems a bit slow so we do not use

        result = data.astype(np.uint8, casting="unsafe", copy=False)
        del data

        if mask_nodata is not None:
            result[mask_nodata] = 0
            del mask_nodata

        result[mask_ge_max] = 255
        result[mask_le_min] = 1
        del mask_ge_max, mask_le_min

        final = red[result] + (green[result] << 8) + (blue[result] << 16) + (a[result] << 24)
        return final

    @staticmethod
    def test_store(path: str):
        store = zarr.storage.MemoryStore(root="hazard.zarr")
        root = zarr.open(store=store, mode="w")
        x, y = np.meshgrid((np.arange(1000) - 500.0) / 500.0, (np.arange(1000) - 500.0) / 500.0)
        im = np.exp(-(x**2 + y**2))
        z = root.create_dataset(  # type: ignore
            path, shape=(1, im.shape[0], im.shape[1]), chunks=(1, im.shape[0], im.shape[1]), dtype="f4"
        )
        z[0, :, :] = im
        return store