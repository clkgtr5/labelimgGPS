#!/usr/bin/env python
# -*- coding: utf8 -*-
import sys
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from lxml import etree
import codecs

XML_EXT = '.xml'
ENCODE_METHOD = 'utf-8'

class PascalVocWriter:

    def __init__(self, foldername, filename, imgSize,databaseSrc='Unknown', localImgPath=None):
        self.foldername = foldername
        self.filename = filename
        self.databaseSrc = databaseSrc
        self.imgSize = imgSize
        self.boxlist = []
        self.localImgPath = localImgPath
        self.verified = False
        self.object_items = {}
        self.latitude = None
        self.longitude = None
        self.altitude = None
    def prettify(self, elem):
        """
            Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf8')
        root = etree.fromstring(rough_string)
        return etree.tostring(root, pretty_print=True, encoding=ENCODE_METHOD).replace("  ".encode(), "\t".encode())
        # minidom does not support UTF-8
        '''reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="\t", encoding=ENCODE_METHOD)'''

    def genXML(self):
        """
            Return XML root
        """
        # Check conditions
        if self.filename is None or \
                self.foldername is None or \
                self.imgSize is None:
            return None

        top = Element('annotation')
        if self.verified:
            top.set('verified', 'yes')

        folder = SubElement(top, 'folder')
        folder.text = self.foldername

        filename = SubElement(top, 'filename')
        filename.text = self.filename

        if self.localImgPath is not None:
            localImgPath = SubElement(top, 'path')
            localImgPath.text = self.localImgPath

        source = SubElement(top, 'source')
        database = SubElement(source, 'database')
        database.text = self.databaseSrc

        size_part = SubElement(top, 'size')
        width = SubElement(size_part, 'width')
        height = SubElement(size_part, 'height')
        depth = SubElement(size_part, 'depth')
        width.text = str(self.imgSize[1])
        height.text = str(self.imgSize[0])
        if len(self.imgSize) == 3:
            depth.text = str(self.imgSize[2])
        else:
            depth.text = '1'

        imgLocation =  SubElement(top, 'Location')
        imgLatitude = SubElement(imgLocation, 'Latitude')
        imgLongitude = SubElement(imgLocation, 'Longitude')
        imgAltitude = SubElement(imgLocation, 'Altitude')
        imgLatitude.text = str(self.latitude)
        imgLongitude.text = str(self.longitude)
        imgAltitude.text = str(self.altitude)



        segmented = SubElement(top, 'segmented')
        segmented.text = '0'
        return top

    def addBndBox(self, xmin, ymin, xmax, ymax, name, difficult, objectItems = None):
        bndbox = {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}
        bndbox['name'] = name
        bndbox['difficult'] = difficult
        try:
            bndbox['latitude'] = objectItems['latitude']
        except:
            bndbox['latitude'] = ""
        try:
            bndbox['longitude'] = objectItems['longitude']
        except:
            bndbox['longitude'] = ""
        try:
            bndbox['altitude'] = objectItems['altitude']
        except:
            bndbox['altitude'] = ""
        try:
            bndbox['superclass'] = objectItems['superclass']
        except:
            bndbox['superclass'] = ""
        try:
            bndbox['subclass'] = objectItems['subclass']
        except:
            bndbox['subclass'] = ""
        try:
            bndbox['SignMainGeneralOID'] = objectItems['SignMainGeneralOID']
        except:
            bndbox['SignMainGeneralOID'] = ""
        try:
            bndbox['ID'] = objectItems['ID']
        except:
            bndbox['ID'] = ""
        try:
            bndbox['LaneDirection'] = objectItems['LaneDirection']
        except:
            bndbox['LaneDirection'] = ""
        try:
            bndbox['Marker'] = objectItems['Marker']
        except:
            bndbox['Marker'] = ""
        try:
            bndbox['City'] = objectItems['City']
        except:
            bndbox['City'] = ""
        try:
            bndbox['County'] = objectItems['County']
        except:
            bndbox['County'] = ""
        try:
            bndbox['District'] = objectItems['District']
        except:
            bndbox['District'] = ""
        try:
            bndbox['STREETNAME'] = objectItems['STREETNAME']
        except:
            bndbox['STREETNAME'] = ""
        try:
            bndbox['MUTCDCode'] = objectItems['MUTCDCode']
        except:
            bndbox['MUTCDCode'] = ""
        try:
            bndbox['Retired'] = objectItems['Retired']
        except:
            bndbox['Retired'] = ""
        try:
            bndbox['Replaced'] = objectItems['Replaced']
        except:
            bndbox['Replaced'] = ""
        try:
            bndbox['SignAge'] = objectItems['SignAge']
        except:
            bndbox['SignAge'] = ""
        try:
            bndbox['TWN_TID'] = objectItems['TWN_TID']
        except:
            bndbox['TWN_TID'] = ""
        try:
            bndbox['TWN_MI'] = objectItems['TWN_MI']
        except:
            bndbox['TWN_MI'] = ""
        try:
            bndbox['QCFLAG'] = objectItems['QCFLAG']
        except:
            bndbox['QCFLAG'] = ""
        try:
            bndbox['MIN_TWN_FMI'] = objectItems['MIN_TWN_FMI']
        except:
            bndbox['MIN_TWN_FMI'] = ""
        try:
            bndbox['MAX_TWN_TMI'] = objectItems['MAX_TWN_TMI']
        except:
            bndbox['MAX_TWN_TMI'] = ""
        try:
            bndbox['SR_SID'] = objectItems['SR_SID']
        except:
            bndbox['SR_SID'] = ""
        try:
            bndbox['OFFSET'] = objectItems['OFFSET']
        except:
            bndbox['OFFSET'] = ""
        try:
            bndbox['PublishDate'] = objectItems['PublishDate']
        except:
            bndbox['PublishDate'] = ""
        self.boxlist.append(bndbox)


    def appendObjects(self, top):
        for each_object in self.boxlist:
            object_item = SubElement(top, 'object')
            name = SubElement(object_item, 'name')
            try:
                name.text = unicode(each_object['name'])
            except NameError:
                # Py3: NameError: name 'unicode' is not defined
                name.text = each_object['name']
            pose = SubElement(object_item, 'pose')
            pose.text = "Unspecified"
            truncated = SubElement(object_item, 'truncated')
            if int(each_object['ymax']) == int(self.imgSize[0]) or (int(each_object['ymin'])== 1):
                truncated.text = "1" # max == height or min
            elif (int(each_object['xmax'])==int(self.imgSize[1])) or (int(each_object['xmin'])== 1):
                truncated.text = "1" # max == width or min
            else:
                truncated.text = "0"
            difficult = SubElement(object_item, 'difficult')
            difficult.text = str( bool(each_object['difficult']) & 1 )

            # add new xml labels
            loaction_item = SubElement(object_item, 'location')
            latitude = SubElement(loaction_item, 'latitude')
            latitude.text = str(each_object['latitude'])
            longitude = SubElement(loaction_item, 'longitude')
            longitude.text = str(each_object['longitude'])

            altitude = SubElement(loaction_item, 'altitude')
            altitude.text = str(each_object['altitude'])

            try:
                superclass = SubElement(object_item, 'superclass')
                superclass.text = str(each_object['superclass'])
                subclass = SubElement(object_item, 'subclass')
                subclass.text = str(each_object['subclass'])
                SignMainGeneralOID = SubElement(object_item, 'SignMainGeneralOID')
                SignMainGeneralOID.text = str(each_object['SignMainGeneralOID'])
                ID = SubElement(object_item, 'ID')
                ID.text = str(each_object['ID'])
                LaneDirection = SubElement(object_item, 'LaneDirection')
                LaneDirection.text = str(each_object['LaneDirection'])
                Marker = SubElement(object_item, 'Marker')
                Marker.text = str(each_object['Marker'])
                City = SubElement(object_item, 'City')
                City.text = str(each_object['City'])
                County = SubElement(object_item, 'County')
                County.text = str(each_object['County'])
                District = SubElement(object_item, 'District')
                District.text = str(each_object['District'])
                STREETNAME = SubElement(object_item, 'STREETNAME')
                STREETNAME.text = str(each_object['STREETNAME'])
                MUTCDCode = SubElement(object_item, 'MUTCDCode')
                MUTCDCode.text = str(each_object['MUTCDCode'])
                Retired = SubElement(object_item, 'Retired')
                Retired.text = str(each_object['Retired'])
                Replaced = SubElement(object_item, 'Replaced')
                Replaced.text = str(each_object['Replaced'])
                SignAge = SubElement(object_item, 'SignAge')
                SignAge.text = str(each_object['SignAge'])
                TWN_TID = SubElement(object_item, 'TWN_TID')
                TWN_TID.text = str(each_object['TWN_TID'])
                TWN_MI = SubElement(object_item, 'TWN_MI')
                TWN_MI.text = str(each_object['TWN_MI'])
                QCFLAG = SubElement(object_item, 'QCFLAG')
                QCFLAG.text = str(each_object['QCFLAG'])
                MIN_TWN_FMI = SubElement(object_item, 'MIN_TWN_FMI')
                MIN_TWN_FMI.text = str(each_object['MIN_TWN_FMI'])
                MAX_TWN_TMI = SubElement(object_item, 'MAX_TWN_TMI')
                MAX_TWN_TMI.text = str(each_object['MAX_TWN_TMI'])
                SR_SID = SubElement(object_item, 'SR_SID')
                SR_SID.text = str(each_object['SR_SID'])
                OFFSET = SubElement(object_item, 'OFFSET')
                OFFSET.text = str(each_object['OFFSET'])
                PublishDate = SubElement(object_item, 'PublishDate')
                PublishDate.text = str(each_object['PublishDate'])
            except Exception as e:
                print('Exception append:',str(e))

            # bndbox xml labels
            bndbox = SubElement(object_item, 'bndbox')
            xmin = SubElement(bndbox, 'xmin')
            xmin.text = str(each_object['xmin'])
            ymin = SubElement(bndbox, 'ymin')
            ymin.text = str(each_object['ymin'])
            xmax = SubElement(bndbox, 'xmax')
            xmax.text = str(each_object['xmax'])
            ymax = SubElement(bndbox, 'ymax')
            ymax.text = str(each_object['ymax'])

    def save(self, targetFile=None):
        root = self.genXML()
        self.appendObjects(root)
        out_file = None
        if targetFile is None:
            out_file = codecs.open(
                self.filename + XML_EXT, 'w', encoding=ENCODE_METHOD)
        else:
            out_file = codecs.open(targetFile, 'w', encoding=ENCODE_METHOD)

        prettifyResult = self.prettify(root)
        out_file.write(prettifyResult.decode('utf8'))
        out_file.close()


class PascalVocReader:

    def __init__(self, filepath):
        # shapes type:
        # [labbel, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], color, color, difficult]
        self.shapes = []
        self.filepath = filepath
        self.verified = False
        try:
            self.parseXML()
        except:
            pass

    def getShapes(self):
        return self.shapes

    def addShape(self, label, bndbox, difficult):
        xmin = int(float(bndbox.find('xmin').text))
        ymin = int(float(bndbox.find('ymin').text))
        xmax = int(float(bndbox.find('xmax').text))
        ymax = int(float(bndbox.find('ymax').text))
        points = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        self.shapes.append((label, points, None, None, difficult))

    def parseXML(self):
        assert self.filepath.endswith(XML_EXT), "Unsupport file format"
        parser = etree.XMLParser(encoding=ENCODE_METHOD)
        xmltree = ElementTree.parse(self.filepath, parser=parser).getroot()
        filename = xmltree.find('filename').text
        try:
            verified = xmltree.attrib['verified']
            if verified == 'yes':
                self.verified = True
        except KeyError:
            self.verified = False

        for object_iter in xmltree.findall('object'):
            try:
                bndbox = object_iter.find("bndbox")
            except:
                bndbox = object_iter.find("object")
            label = object_iter.find('name').text
            # Add chris
            difficult = False
            if object_iter.find('difficult') is not None:
                difficult = bool(int(object_iter.find('difficult').text))
            self.addShape(label, bndbox, difficult)
        return True
