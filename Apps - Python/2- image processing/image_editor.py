from ex5_helper import *
from typing import Optional

def separate_channels(image: ColoredImage) -> List[SingleChannelImage]:
    channels = len(image)
    columns = len(image[0])
    rows = len(image[0][0])

    separated_channels = []
    for row in range(rows):
        single_channel_image = []
        for channel in range(channels):
            single_column = []
            for col in range(columns):
                single_column.append(image[channel][col][row])
            single_channel_image.append(single_column)
        separated_channels.append(single_channel_image)

    return separated_channels

def combine_channels(channels: List[SingleChannelImage]) -> ColoredImage:
    rows = len(channels[0])
    columns = len(channels[0][0])
    num_channels = len(channels)

    colored_image = [[[0 for _ in range(num_channels)] for _ in range(columns)] for _ in range(rows)]

    for row in range(rows):
        for col in range(columns):
            for channel in range(num_channels):
                colored_image[row][col][channel] = channels[channel][row][col]

    return colored_image

def RGB2grayscale(colored_image: ColoredImage) -> SingleChannelImage:
    rows = len(colored_image)
    columns = len(colored_image[0])
    
    grayscale_image = [[0 for _ in range(columns)] for _ in range(rows)]

    for row in range(rows):
        for col in range(columns):
            red = colored_image[row][col][0]
            green = colored_image[row][col][1]
            blue = colored_image[row][col][2]
            
            grayscale_image[row][col] = round(red * 0.299 + green * 0.587 + blue * 0.114)

    return grayscale_image

def blur_kernel(size: int) -> Kernel:
    value = 1 / (size * size)
    kernel = [[value for _ in range(size)] for _ in range(size)]
    
    return kernel
    
def apply_kernel(image: SingleChannelImage, kernel: Kernel) -> SingleChannelImage:
    rows = len(image)
    cols = len(image[0])
    kernel_size = len(kernel)
    kernel_radius = kernel_size // 2
    result = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        for j in range(cols):
            total = 0
            divisor = 0
            for ki in range(kernel_size):
                for kj in range(kernel_size):
                    ni = i + ki - kernel_radius
                    nj = j + kj - kernel_radius
                    if ni < 0 or ni >= rows or nj < 0 or nj >= cols: # out of bounds
                        total += image[i][j] * kernel[ki][kj]
                    else:
                        total += image[ni][nj] * kernel[ki][kj]
                    divisor += kernel[ki][kj]

            result[i][j] = min(255, max(0, round(total / divisor)))

    return result

def bilinear_interpolation(image: SingleChannelImage, y: float, x: float) -> int:
    x0, y0 = int(x), int(y)
    dx, dy = x - x0, y - y0

    intensity_tl = image[y0][x0]
    intensity_tr = image[y0][min(x0 + 1, len(image[0]) - 1)]
    intensity_bl = image[min(y0 + 1, len(image) - 1)][x0]
    intensity_br = image[min(y0 + 1, len(image) - 1)][min(x0 + 1, len(image[0]) - 1)]

    intensity_top = intensity_tl * (1 - dx) + intensity_tr * dx
    intensity_bottom = intensity_bl * (1 - dx) + intensity_br * dx
    interpolated_intensity = intensity_top * (1 - dy) + intensity_bottom * dy

    return round(interpolated_intensity)

def resize(image: SingleChannelImage, new_height: int, new_width: int) -> SingleChannelImage:
    height, width = len(image), len(image[0])
    resized_image = [[0] * new_width for _ in range(new_height)]

    for i in range(new_height):
        for j in range(new_width):
            src_i = i * height / new_height
            src_j = j * width / new_width

            top_left_i, top_left_j = int(src_i), int(src_j)
            bottom_right_i, bottom_right_j = min(top_left_i + 1, height - 1), min(top_left_j + 1, width - 1)

            dx = src_j - top_left_j
            dy = src_i - top_left_i

            top_left_val = image[top_left_i][top_left_j]
            top_right_val = image[top_left_i][bottom_right_j]
            bottom_left_val = image[bottom_right_i][top_left_j]
            bottom_right_val = image[bottom_right_i][bottom_right_j]

            interpolated_val = (1 - dx) * (1 - dy) * top_left_val + dx * (1 - dy) * top_right_val + \
                               (1 - dx) * dy * bottom_left_val + dx * dy * bottom_right_val

            resized_image[i][j] = round(interpolated_val)

    return resized_image

def rotate_90(image: Image, direction: str) -> Image:
    if direction == 'R':
        rotated_image = image[::-1]

    elif direction == 'L':
        rotated_image = [row[::-1] for row in image]

    return [[rotated_image[j][i] for j in range(len(rotated_image))] for i in range(len(rotated_image[0]))]

def get_best_match(image: SingleChannelImage, patch: SingleChannelImage) -> tuple:
    patch_height, patch_width = len(patch), len(patch[0])
    image_height, image_width = len(image), len(image[0])
    min_distance = float('inf')
    best_match_position = (0, 0)

    for i in range(image_height - patch_height + 1):
        for j in range(image_width - patch_width + 1):
            squared_diff_sum = 0
            for pi in range(patch_height):
                for pj in range(patch_width):
                    diff = image[i + pi][j + pj] - patch[pi][pj]
                    squared_diff_sum += diff * diff

            mean_squared_diff = squared_diff_sum / (patch_height * patch_width)

            if mean_squared_diff < min_distance:
                min_distance = mean_squared_diff
                best_match_position = (i, j)

    return (best_match_position, min_distance)

def find_patch_in_img(image: SingleChannelImage, patch: SingleChannelImage) -> dict:
    best_match_position, distance = get_best_match(image, patch)
    return {'position': best_match_position, 'distance': distance}

if __name__ == '__main__':
    # separate_channels:
    print('separate_channels test:\n')

    image = [[[1, 2]]]
    print(separate_channels(image))

    image = [[[1, 2, 3], [1, 2, 3], [1, 2, 3]],
             [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
             [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
             [[1, 2, 3], [1, 2, 3], [1, 2, 3]]]
    
    print(separate_channels(image))
    print('--------------------------------------')

    # combine_channels
    print('combine_channels test:\n')

    image_list = [[[1]], [[2]]]
    print(combine_channels(image_list))

    image_list = [[[1, 1, 1], [1, 1, 1], [1, 1, 1], [1, 1, 1]], 
                  [[2, 2, 2], [2, 2, 2], [2, 2, 2], [2, 2, 2]], 
                  [[3, 3, 3], [3, 3, 3], [3, 3, 3], [3, 3, 3]]]
                
    print(combine_channels(image_list))
    print('--------------------------------------')

    # RGB2grayscale
    print('RGB2grayscale test:\n')
    print(RGB2grayscale([[[100, 180, 240]]]))
    print(RGB2grayscale([[[200, 0, 14], [15, 6, 50]]]))
    print('--------------------------------------')

    # blur_kernel
    print('blur_kernel test:\n')
    print(blur_kernel(3))
    print('--------------------------------------')

    # apply_kernel
    print('apply_kernel test:\n')
    print(apply_kernel([[0, 128, 255]], blur_kernel(3)))
    
    print(apply_kernel([[10, 20, 30, 40, 50],
                        [8, 16, 24, 32, 40],
                        [6, 12, 18, 24, 30],
                        [4, 8, 12, 16, 20]], blur_kernel(5)))
    print('--------------------------------------')

    # bilinear_interpolation
    print('bilinear_interpolation test:\n')
    print(bilinear_interpolation([[0, 64], [128, 255]], 0, 0))
    print(bilinear_interpolation([[0, 64], [128, 255]], 1, 1))
    print(bilinear_interpolation([[0, 64], [128, 255]], 0.5, 0.5))
    print(bilinear_interpolation([[0, 64], [128, 255]], 0.5, 1))
    print(bilinear_interpolation([[15, 30, 45, 60, 75], [90, 105, 120, 135, 150], [165, 180, 195, 210, 225]], 4/5, 8/3))
    print('--------------------------------------')

    # resize
    print('resize test:\n')
    image = [[10, 20, 30],
         [40, 50, 60],
         [70, 80, 90]]

    print(resize(image, 5, 5))
    print('--------------------------------------')

    # rotate
    print('rotate test:\n')
    print(rotate_90([[1, 2, 3],
                     [4, 5, 6]], 'R'))

    print(rotate_90([[1, 2, 3],
                     [4, 5, 6]], 'L'))

    print(rotate_90([[[1, 2, 3], [4, 5, 6]],
                     [[0, 5, 9], [255, 200, 7]]], 'L'))
    print('--------------------------------------')

    # get_best_match
    print('get_best_match test:\n')
    image = [[1, 5, 1, 3],
            [7, 4, 6, 2],
            [0, 10, 2, 200],
            [250, 9, 0, 240]]

    patch = [[7, 4, 6],
            [0, 10, 3],
            [249, 9, 1]]

    print(get_best_match(image, patch))
    print('--------------------------------------')

    # find_patch_in_img
    print('find_patch_in_img test:\n')

    image = [[1, 5, 1, 3],
            [7, 4, 6, 2],
            [0, 10, 2, 200],
            [250, 9, 0, 240]]
    
    patch = [[7, 4, 6],
            [0, 10, 3],
            [249, 9, 1]]
    
    print(find_patch_in_img(image, patch))
    print('--------------------------------------')