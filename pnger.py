from collections import namedtuple
import zlib
from filters import Filters

class InvalidPNG(Exception):
    pass

# TODO: Make dict to hold the different filter types

PIXELS = {
    0: namedtuple('Pixel', ['gray']),
    2: namedtuple('Pixel', ['red', 'green', 'blue']),
    # 3: A Palette index,
    4: namedtuple('Pixel', ['gray', 'alpha']),
    6: namedtuple('Pixel', ['red', 'green', 'blue', 'alpha'])
}

Posn = namedtuple('Posn', ['x', 'y'])

def filter_algorithm(type, current_byte, index_in_scanline, reconstructed_scanline):
    if type == 0:
        return current_byte
    elif type == 1:
        ''' Recon(x) = Filt(x) + Recon(a)
            Filt(x) is the current_byte
            Recon(a) is the byte in the same positions in 
            the previous reconstructed pixel
        '''
        filt_x = current_byte
        a = index_in_scanline - bytes_per_pixel
        recon_a = 0 if (a < 0) else reconstructed_scanline[a]
        return int(current_byte + recon_a)

def split_into_chunks(file_bytes, chunks=[]):
    ''' chunks should look like this:
        {'length': int, 'type': str, 'data': bytes, 'crc': int}
    '''
    if not file_bytes:
        return chunks

    chunk_data_length = int.from_bytes(file_bytes[0:4], 'big')
    data_end = 8 + chunk_data_length # 8 bytes for the length and the type
    chunk_end = data_end + 4 # The 4 bytes represent the crc
    chunk_type = file_bytes[4:8].decode('utf-8')
    chunk_data = file_bytes[8:data_end]
    chunck_crc = file_bytes[data_end:chunk_end]

    chunk = {
        'length': chunk_data_length,
        'type': chunk_type,
        'data': chunk_data,
        'crc': chunck_crc
    }

    chunks.append(chunk)

    return split_into_chunks(file_bytes[chunk_end:], chunks)

def parse_ihdr_data(ihdr_chunk):
    ihdr_data = ihdr_chunk.get('data')
    Header = namedtuple(
        'Header',
        ['width', 'height', 'bit_depth', 'color_type','compression_type',
        'filter_type', 'interlace_type'])    

    return Header(
        width=int.from_bytes(ihdr_data[0:4], 'big'),
        height=int.from_bytes(ihdr_data[4:8], 'big'),
        bit_depth=ihdr_data[8],
        color_type=ihdr_data[9],
        compression_type=ihdr_data[10],
        filter_type = ihdr_data[11],
        interlace_type = ihdr_data[12]
    )

def parse_chunks(chunks):
    try:
        image_header = parse_ihdr_data([
            chunk for chunk in chunks 
            if chunk.get('type') == 'IHDR'
        ][0])
    except IndexError as err:
        raise InvalidPNG('Missing IHDR chunk')

    try:
        image_data = zlib.decompress(
            b''.join([
                idat.get('data')
                for idat in [
                    chunk for chunk in chunks 
                    if chunk.get('type') == 'IDAT']]))
    except IndexError as err:
        raise InvalidPNG('Invalid IDAT chunks')

    return image_header, image_data

def split_scanlines(width, height, bytes_per_pixel, data):
    scanline_length = width * bytes_per_pixel + 1

    return [
        {'type': scanline[0], 'bytes': scanline[1:]}
        for scanline in [
            data[(scanline_length * i):(scanline_length * (i + 1))]
            for i in range(height)]]

def reconstruct(scanlines, bytes_per_pixel):
    reconstructed = []
    for y, scanline in enumerate(scanlines):
        filter_func = Filters[scanline.get('type')]
        reconstructed_line = []
        reconstructed.append(reconstructed_line)
        for x, byte in enumerate(scanline.get('bytes')):
            position = Posn(x, y)
            reconstructed_byte = filter_func(
                scanlines, position, 'reconstruct', bytes_per_pixel, reconstructed)
            reconstructed_line.append(reconstructed_byte)

    return reconstructed

def create_pixels(Pixel, scanline, bytes_per_pixel):
    pixel_range = range(len(scanline))[::bytes_per_pixel]

    return [
        Pixel(*scanline[pixel_index:pixel_range[i+1]])
        for i, pixel_index in enumerate(pixel_range[:-1])]

if __name__ == '__main__':
    with open('test.png', 'rb') as file:
        image = file.read()

    valid_png_header = b'\x89PNG\r\n\x1a\n'

    if image[0:8] != valid_png_header:
        raise InvalidPNG('not a valid header')

    image_header, image_data = parse_chunks(split_into_chunks(image[8:]))

    try:
        Pixel = PIXELS[image_header.color_type]
    except KeyError as err:
        raise UnemplementedError('I haven\'t done that yet.')
    else:
        bytes_per_pixel = int(
            len(Pixel._fields) * (image_header.bit_depth / 8))

    scanlines = split_scanlines(
        image_header.width,
        image_header.height,
        bytes_per_pixel, 
        image_data
    )

    reconstructed_scanlines = reconstruct(scanlines, bytes_per_pixel)

    pixels = [create_pixels(Pixel, scanline, bytes_per_pixel) for scanline in reconstructed_scanlines]

