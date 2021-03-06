import math
import os
import warnings

from PIL import Image as PIL_Image
from PIL import ImageDraw

from nider.core import MultilineTextUnit
from nider.core import SingleLineTextUnit

from nider.utils import get_random_bgcolor
from nider.utils import get_random_texture
from nider.utils import is_path_creatable

from nider.colors import color_to_rgb
from nider.colors import get_img_dominant_color
from nider.colors import generate_opposite_color
from nider.colors import blend

from nider.exceptions import ImageGeneratorException
from nider.exceptions import ImageSizeFixedWarning
from nider.exceptions import AutoGeneratedUnitColorUsedWarning
from nider.exceptions import AutoGeneratedUnitOutlinecolorUsedWarning


class Header(MultilineTextUnit):
    '''Base class for the header unit'''


class Paragraph(MultilineTextUnit):
    '''Base class for the paragraph unit'''


class Linkback(SingleLineTextUnit):
    '''Class that represents a linkback used in images

    Attributes:
        bottom_padding (int): padding to step back from the bottom of the image.
    '''

    def __init__(self, text, bottom_padding=20, *args, **kwargs):
        self.bottom_padding = bottom_padding
        super().__init__(text=text, *args, **kwargs)

    def _set_height(self):
        '''Sets linkback\'s height'''
        super()._set_height()
        self.height += self.bottom_padding


class Content:
    '''Class that aggregates different units into a sigle object'''
    # Variable to check if the content fits into the img. Default is true,
    # but it may changed by in Img._fix_image_size()
    fits = True

    def __init__(self, paragraph=None, header=None, linkback=None, padding=45):
        if not any((paragraph, header, linkback)):
            raise ImageGeneratorException(
                'Content has to consist at least of one unit.')
        self.para = paragraph
        self.header = header
        self.linkback = linkback
        self.padding = padding
        self.depends_on_opposite_to_bg_color = not all(
            unit.color for unit in [
                self.para, self.header, self.linkback
            ] if unit
        )
        self._set_content_height()

    def _set_content_height(self):
        '''Sets content\'s height'''
        self.height = 0
        if self.para:
            self.height += 2 * self.padding + self.para.height
        if self.header:
            self.height += 1 * self.padding + self.header.height
        if self.linkback:
            self.height += self.linkback.height


class Image:
    '''Base class for a text based image

    Attributes:
        content (nider.models.Content): object that has units to be rendered.
        fullpath (str): path where the image has to be saved.
        width (int): width of the image.
        height (int): height of the image.
        title (str): title of the image. Serves as metadata for latter rendering in html. May be used as alt text of the image. If no title is provided content.header.text will be set as the value.
        description (str): description of the image. Serves as metadata for latter rendering in html. May be used as description text of the image. If no description is provided content.paragraph.text will be set as the value.
    '''

    def __init__(self, content, fullpath, width=1080, height=1080, title=None, description=None):
        self._set_content(content)
        self._set_fullpath(fullpath)
        self._set_image_size(width, height)
        self._set_title(title)
        self._set_description(description)

    def draw_on_texture(self, texture_path=None):
        '''Draws preinitialized image and its attributes on a texture

        Draws preinitiated image and its attributes on a texture. If texture_path
        is set to None, takes random textures from textures/

        Attributes:
            texture_path (str): path of the texture to use.
        '''
        if texture_path is None:
            texture_path = get_random_texture()
        elif not os.path.isfile(texture_path):
            raise FileNotFoundError(
                'Can\'t find texture {}. Please, choose an existing texture'.format(texture_path))
        if self.content.depends_on_opposite_to_bg_color:
            self.opposite_to_bg_color = generate_opposite_color(
                get_img_dominant_color(texture_path)
            )
        self._create_image()
        self._create_draw_object()
        self._fill_image_with_texture(texture_path)
        self._draw_content()
        self._save()

    def draw_on_bg(self, bgcolor=None):
        '''Draws preinitialized image and its attributes on a colored background

        Draws preinitiated image and its attributes on a colored background. If bgcolor
        is set to None, random nider.colors.colormap.FLAT_UI color is generated

        Attributes:
            bgcolor (str, tuple): either hex or rgb representation of background color.
        '''
        self.bgcolor = color_to_rgb(
            bgcolor) if bgcolor else get_random_bgcolor()
        if self.content.depends_on_opposite_to_bg_color:
            self.opposite_to_bg_color = generate_opposite_color(self.bgcolor)
        self._create_image()
        self._create_draw_object()
        self._fill_image_with_color()
        self._draw_content()
        self._save()

    def draw_on_image(self, image_path, image_enhancements=None, image_filters=None):
        '''Draws preinitialized image and its attributes on an image

        Attributes:
            image_path (str): path of the image to draw on.
            image_enhancements (itarable): itarable of tuples, each containing a class from PIL.ImageEnhance that will be applied and factor - a floating point value controlling the enhancement. Check docs of PIL.ImageEnhance for more info.
            image_filters (itarable): itarable of filters from PIL.ImageFilter that will be applied. Check docs of PIL.ImageFilter for more info.
        '''
        if not os.path.isfile(image_path):
            raise FileNotFoundError(
                'Can\'t find image {}. Please, choose an existing image'.format(image_path))
        self.image = PIL_Image.open(image_path)
        if self.content.depends_on_opposite_to_bg_color:
            self.opposite_to_bg_color = generate_opposite_color(
                get_img_dominant_color(image_path)
            )
        if image_filters:
            for image_filter in image_filters:
                self.image = self.image.filter(image_filter)
        if image_enhancements:
            for enhancement in image_enhancements:
                enhance_method, enhance_factor = enhancement[0], enhancement[1]
                enhancer = enhance_method(self.image)
                self.image = enhancer.enhance(enhance_factor)
        self._create_draw_object()
        self.width, self.height = self.image.size
        self._draw_content()
        self._save()

    def _save(self):
        '''Saves the image'''
        self.image.save(self.fullpath)

    def _set_content(self, content):
        '''Sets content used in the image'''
        self.content = content
        self.header = content.header
        self.para = content.para
        self.linkback = content.linkback

    def _set_fullpath(self, fullpath):
        '''Sets path where to save the image'''
        if is_path_creatable(fullpath):
            self.fullpath = fullpath
        else:
            raise AttributeError(
                "Is seems impossible to create a file in path {}".format(fullpath))

    def _set_image_size(self, width, height):
        '''Sets width and height of the image'''
        if width <= 0 or height <= 0:
            raise AttributeError(
                "Width or height of the image have to be positive integers")
        self.width = width
        self.height = height

    def _set_title(self, title):
        '''Sets title of the image'''
        if title:
            self.title = title
        elif self.content.header:
            self.title = self.content.header.text
        else:
            self.title = ''

    def _set_description(self, description):
        '''Sets description of the image'''
        if description:
            self.description = description
        elif self.content.para:
            self.description = self.content.para.text
        else:
            self.description = ''

    def _fix_image_size(self):
        '''Fixes image's size'''

        if self.content.height >= self.height:
            warnings.warn(ImageSizeFixedWarning())
            self.content.fits = False
            self.height = self.content.height

    def _create_image(self):
        '''Creates a basic PIL image

        Creates a basic PIL image previously fixing its size
        '''
        self._fix_image_size()
        self.image = PIL_Image.new("RGBA", (self.width, self.height))

    def _create_draw_object(self):
        '''Creates a basic PIL Draw object'''
        self.draw = ImageDraw.Draw(self.image)

    def _fill_image_with_texture(self, texture_path):
        '''Fills an image with a texture

        Fills an image with a texture by reapiting it necessary number of times

        Attributes:
            texture_path (str): path of the texture to use
        '''
        texture = PIL_Image.open(texture_path, 'r')
        texture_w, texture_h = texture.size
        bg_w, bg_h = self.image.size
        times_for_Ox = math.ceil(bg_w / texture_w)
        times_for_Oy = math.ceil(bg_h / texture_h)
        for y in range(times_for_Oy):
            for x in range(times_for_Ox):
                offset = (x * texture_w, y * texture_h)
                self.image.paste(texture, offset)

    def _fill_image_with_color(self):
        '''Fills an image with a color

        Fills an image with a color by creating a colored rectangle of the image
        size
        '''
        self.draw.rectangle([(0, 0), self.image.size], fill=self.bgcolor)

    def _prepare_content(self):
        '''Prepares content for drawing'''
        content = self.content
        for unit in [content.header, content.para, content.linkback]:
            if unit:
                if not unit.color:
                    color_to_use = self.opposite_to_bg_color
                    # explicitly sets unit's color to disntinc to bg one
                    unit.color = color_to_use
                    warnings.warn(
                        AutoGeneratedUnitColorUsedWarning(unit, color_to_use))
                if unit.outline and not unit.outline.color:
                    color_to_use = blend(unit.color, '#000', 0.2)
                    unit.outline.color = color_to_use
                    warnings.warn(
                        AutoGeneratedUnitOutlinecolorUsedWarning(unit, color_to_use))

    def _draw_content(self):
        '''Draws each unit of the content on the image'''
        self._prepare_content()
        if self.header:
            self._draw_header()
        if self.para:
            self._draw_para()
        if self.linkback:
            self._draw_linkback()

    def _draw_header(self):
        '''Draws the header on the image'''
        current_h = self.content.padding
        self._draw_unit(current_h, self.header)

    def _draw_para(self):
        '''Draws the paragraph on the image'''
        if self.content.fits:
            # Trying to center everything
            current_h = math.floor(
                (self.height - self.para.height) / 2)
            self._draw_unit(current_h, self.para)
        else:
            if self.header:
                header_with_padding_height = 2 * self.content.padding + self.header.height
                current_h = header_with_padding_height
            else:
                current_h = self.content.padding
            self._draw_unit(current_h, self.para)

    def _draw_linkback(self):
        '''Draws a linkback on the image'''
        current_h = self.height - self.linkback.height
        self._draw_unit(current_h, self.linkback)

    def _draw_unit(self, start_height, unit):
        '''Draws the text and its outline on the image starting at specific height'''
        current_h = start_height
        try:
            lines = unit.wrapped_lines
        except AttributeError:
            # text is a one-liner. Construct a list out of it for later usage
            lines = [unit.text]
        line_padding = getattr(unit, 'line_padding', None)
        outline = unit.outline
        font = unit.font

        for line in lines:
            w, h = self.draw.textsize(line, font=unit.font)
            if unit.align == "center":
                x = (self.width - w) / 2
            elif unit.align == "left":
                x = self.width * 0.075
            elif unit.align == "right":
                x = 0.925 * self.width - w
            y = current_h

            if outline:
                # thin border
                self.draw.text((x - outline.width, y), line, font=font,
                               fill=outline.color)
                self.draw.text((x + outline.width, y), line, font=font,
                               fill=outline.color)
                self.draw.text((x, y - outline.width), line, font=font,
                               fill=outline.color)
                self.draw.text((x, y + outline.width), line, font=font,
                               fill=outline.color)

                # thicker border
                self.draw.text((x - outline.width, y - outline.width), line,
                               font=font, fill=outline.color)
                self.draw.text((x + outline.width, y - outline.width), line,
                               font=font, fill=outline.color)
                self.draw.text((x - outline.width, y + outline.width), line,
                               font=font, fill=outline.color)
                self.draw.text((x + outline.width, y + outline.width), line,
                               font=font, fill=outline.color)

            self.draw.text((x, y), line, unit.color, font=font)

            if line_padding:
                current_h += h + line_padding


class FacebookSquarePost(Image):
    '''Alias of models.Image with width=470 and height=470'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 470)
        kwargs['height'] = kwargs.get('height', 470)
        super().__init__(*args, **kwargs)


class FacebookLandscapePost(Image):
    '''Alias of models.Image with width=1024 and height=512'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 1024)
        kwargs['height'] = kwargs.get('height', 512)
        super().__init__(*args, **kwargs)


TwitterPost = FacebookLandscapePost


class TwitterLargeCard(Image):
    '''Alias of models.Image with width=506 and height=506'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 506)
        kwargs['height'] = kwargs.get('height', 506)
        super().__init__(*args, **kwargs)


class InstagramSquarePost(Image):
    '''Alias of models.Image with width=1080 and height=1080'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 1080)
        kwargs['height'] = kwargs.get('height', 1080)
        super().__init__(*args, **kwargs)


class InstagramPortraitPost(Image):
    '''Alias of models.Image with width=1080 and height=1350'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 1080)
        kwargs['height'] = kwargs.get('height', 1350)
        super().__init__(*args, **kwargs)


class InstagramLandscapePost(Image):
    '''Alias of models.Image with width=1080 and height=566'''

    def __init__(self, *args, **kwargs):
        kwargs['width'] = kwargs.get('width', 1080)
        kwargs['height'] = kwargs.get('height', 566)
        super().__init__(*args, **kwargs)
