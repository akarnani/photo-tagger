"""Tests for XMP sidecar file functionality"""

import pytest
import tempfile
import os
from lxml import etree

from photo_tagger.image_processor import ImageProcessor


class TestXMPProcessor:
    
    def create_test_image_file(self, extension='.jpg'):
        """Helper to create temporary image file"""
        temp_file = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
        temp_file.close()
        return temp_file.name
    
    def create_test_xmp_content(self, keywords):
        """Helper to create test XMP content"""
        keyword_items = '\n'.join([f'     <rdf:li>{keyword}</rdf:li>' for keyword in keywords])
        
        return f'''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 5.5.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:lightroom="http://ns.adobe.com/lightroom/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:exif="http://ns.adobe.com/exif/1.0/">
   <xmp:Rating>0</xmp:Rating>
   <lightroom:hierarchicalSubject>
    <rdf:Bag>
{keyword_items}
    </rdf:Bag>
   </lightroom:hierarchicalSubject>
   <dc:subject>
    <rdf:Bag>
{keyword_items}
    </rdf:Bag>
   </dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''
    
    def test_create_xmp_sidecar_new_file(self):
        """Test creating new XMP sidecar file"""
        image_path = self.create_test_image_file()
        xmp_path = os.path.splitext(image_path)[0] + '.xmp'
        
        try:
            processor = ImageProcessor(image_path)
            keywords = ['Test Site', 'Diving']
            
            success = processor.create_xmp_sidecar(keywords, dry_run=False)
            
            assert success is True
            assert os.path.exists(xmp_path)
            
            # Parse and verify XMP content
            tree = etree.parse(xmp_path)
            root = tree.getroot()
            
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'lightroom': 'http://ns.adobe.com/lightroom/1.0/'
            }
            
            # Check dc:subject keywords
            dc_keywords = root.xpath('//dc:subject/rdf:Bag/rdf:li/text()', namespaces=namespaces)
            assert 'Test Site' in dc_keywords
            assert 'Diving' in dc_keywords
            
            # Check lightroom:hierarchicalSubject keywords
            lr_keywords = root.xpath('//lightroom:hierarchicalSubject/rdf:Bag/rdf:li/text()', namespaces=namespaces)
            assert 'Test Site' in lr_keywords
            assert 'Diving' in lr_keywords
            
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)
            if os.path.exists(xmp_path):
                os.unlink(xmp_path)
    
    def test_create_xmp_sidecar_existing_file(self):
        """Test updating existing XMP sidecar file with new keywords"""
        image_path = self.create_test_image_file()
        xmp_path = os.path.splitext(image_path)[0] + '.xmp'
        
        try:
            # Create existing XMP file with some keywords
            existing_content = self.create_test_xmp_content(['Existing Keyword', 'Old Site'])
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(existing_content)
            
            processor = ImageProcessor(image_path)
            new_keywords = ['New Site', 'Existing Keyword']  # One duplicate, one new
            
            success = processor.create_xmp_sidecar(new_keywords, dry_run=False)
            
            assert success is True
            
            # Parse and verify merged keywords
            tree = etree.parse(xmp_path)
            root = tree.getroot()
            
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            dc_keywords = root.xpath('//dc:subject/rdf:Bag/rdf:li/text()', namespaces=namespaces)
            
            # Should have all unique keywords
            assert 'Existing Keyword' in dc_keywords
            assert 'Old Site' in dc_keywords
            assert 'New Site' in dc_keywords
            assert len([k for k in dc_keywords if k == 'Existing Keyword']) == 1  # No duplicates
            
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)
            if os.path.exists(xmp_path):
                os.unlink(xmp_path)
    
    def test_create_xmp_sidecar_dry_run(self):
        """Test dry run mode doesn't create files"""
        image_path = self.create_test_image_file()
        xmp_path = os.path.splitext(image_path)[0] + '.xmp'
        
        try:
            processor = ImageProcessor(image_path)
            keywords = ['Test Site']
            
            success = processor.create_xmp_sidecar(keywords, dry_run=True)
            
            assert success is True
            assert not os.path.exists(xmp_path)
            
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)
            if os.path.exists(xmp_path):
                os.unlink(xmp_path)
    
    def test_read_existing_xmp_keywords(self):
        """Test reading keywords from existing XMP file"""
        image_path = self.create_test_image_file()
        xmp_path = os.path.splitext(image_path)[0] + '.xmp'
        
        try:
            # Create XMP file with known keywords
            test_keywords = ['Reef Dive', 'Blue Water', 'Coral Garden']
            xmp_content = self.create_test_xmp_content(test_keywords)
            
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write(xmp_content)
            
            processor = ImageProcessor(image_path)
            existing_keywords = processor._read_existing_xmp_keywords(xmp_path)
            
            assert len(existing_keywords) == 3
            for keyword in test_keywords:
                assert keyword in existing_keywords
                
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)
            if os.path.exists(xmp_path):
                os.unlink(xmp_path)
    
    def test_read_existing_xmp_keywords_invalid_file(self):
        """Test handling of invalid XMP file"""
        image_path = self.create_test_image_file()
        xmp_path = os.path.splitext(image_path)[0] + '.xmp'
        
        try:
            # Create invalid XML file
            with open(xmp_path, 'w', encoding='utf-8') as f:
                f.write('This is not valid XML')
            
            processor = ImageProcessor(image_path)
            existing_keywords = processor._read_existing_xmp_keywords(xmp_path)
            
            # Should return empty list for invalid file
            assert existing_keywords == []
                
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)
            if os.path.exists(xmp_path):
                os.unlink(xmp_path)
    
    def test_xmp_content_format(self):
        """Test that generated XMP content is well-formed XML"""
        image_path = self.create_test_image_file()
        
        try:
            processor = ImageProcessor(image_path)
            keywords = ['Test Site', 'Underwater Photography']
            
            xmp_content = processor._create_xmp_content(keywords)
            
            # Parse to ensure well-formed XML
            root = etree.fromstring(xmp_content.encode('utf-8'))
            
            # Verify structure
            assert root.tag == '{adobe:ns:meta/}xmpmeta'
            
            # Check namespaces are declared
            rdf_elements = root.xpath('//rdf:RDF', namespaces={'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'})
            assert len(rdf_elements) == 1
            
        finally:
            if os.path.exists(image_path):
                os.unlink(image_path)