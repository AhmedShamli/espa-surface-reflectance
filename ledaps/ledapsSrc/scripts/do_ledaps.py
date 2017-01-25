#! /usr/bin/env python
import sys
import os
import re
import commands
import datetime
import logging
from optparse import OptionParser

ERROR = 1
SUCCESS = 0


############################################################################
# Description: isLeapYear will determine if the specified year is a leap
# year.
#
# Inputs:
#   year - year to determine if it is a leap year (integer)
#
# Returns:
#     1 - yes, this is a leap year
#     0 - no, this is not a leap year
#
# Notes:
############################################################################
def isLeapYear(year):
    if (year % 4) == 0:
        if (year % 100) == 0:
            if (year % 400) == 0:
                return True
            else:
                return False
        else:
            return True
    else:
        return False


#############################################################################
# Created on November 13, 2012 by Gail Schmidt, USGS/EROS
# Created Python script so that lnd* application status values can be checked
# for successful completion and failures can be flagged.
#
# History:
#   Updated on 11/29/2012 by Gail Schmidt, USGS/EROS
#   Created the Ledaps class and added modules to run the LEDAPS code and
#       determine if the proper ancillary data exists for a requested year
#       and year/doy.
#   Updated on 12/6/2012 by Gail Schmidt, USGS/EROS
#   Modified the run_ledaps method to change to the XML directory
#       before running the LEDAPS software, and then return to the current
#       directory upon successful or failure exit.
#   Updated on 3/7/2014 by Gail Schmidt, USGS/EROS
#   Modified the run_ledaps script to work with the input XML file as
#       part of the switch to utilize the ESPA internal raw binary file
#   Updated on 10/09/2014 by Ron Dilley, USGS/EROS
#   Modified to be pep8 compliant.
#   Updated on 11/12/2015 by Nathan Genetzky, USGS/EROS
#   Modified to use the Python logger vs. print statements
#   Updated on 11/13/2015 by Gail Schmidt, USGS/EROS
#   Removed the --usebin command-line option.  All executables for LEDAPS
#       will be expected in the PATH.
#   Updated on 9/7/2016 by Gail Schmidt, USGS/EROS
#   Modified to flag collection scenes for special handling of QA output
#       in LEDAPS processing. Additional command-line option is passed to
#       the lndsr executable. Also, collection processing will not include
#       the lndsrbm post-processing of the QA, since the goal is to represent
#       the QA which was used for surface reflectance corrections.
#
# Usage: do_ledaps.py --help prints the help message
############################################################################
class Ledaps():

    def __init__(self):
        pass

    ########################################################################
    # Description: findAncillary will parse the ANC_PATH directory and verify
    # that the required NCEP REANALYSIS and EP/TOMS ancillary products are
    # available for the specified year and DOY.  If the DOY is not specified,
    # then the entire year will be processed.
    #
    # Inputs:
    #   year - which year to look for ancillary data (integer)
    #   doy - which DOY to look for ancillary data (integer)
    #         (default - parse all days in the specified year)
    #
    # Returns:
    #     None - error occurred while processing the specified year/doy
    #     list of True/False - current value is True if the ancillary data is
    #         available for the current year/doy, False if the ancillary data
    #         does not exist;  if the DOY was specified, then the list will
    #         only have one value
    #
    # Notes:
    #     ANC_PATH points to the base LEDAPS ancillary directory which
    #         contains the REANALYSIS and EP/TOMS subdirectories.
    #######################################################################
    def findAncillary(self, year, doy=-99):
        logger = logging.getLogger(__name__)
        # determine the ancillary directory to store the data
        ancdir = os.environ.get('ANC_PATH')
        if ancdir is None:
            logger.error('ANC_PATH environment variable not set... exiting')
            return None

        # initialize the doyList to empty and the number of days to 1
        doyList = []
        ndays = 1

        # if doy wasn't specified, then determine the number of days in the
        # specified year. if the specified year is the current year, only
        # process up through today otherwise process through all the days
        # in the year
        if doy == -99:
            now = datetime.datetime.now()
            if year == now.year:
                ndays = now.timetuple().tm_yday
            else:
                if isLeapYear(year) is True:
                    ndays = 366
                else:
                    ndays = 365

        # loop through the number of days and determine if the required
        # ancillary data exists
        for currdoy in range(1, ndays+1):
            # if the DOY was specified then use that value otherwise use
            # the current DOY based on the number of days to be processed
            if doy != -99:
                currdoy = doy

            # pad the DOY with 0s if needed
            if currdoy < 10:
                dayofyear = '00' + str(currdoy)
            elif 9 < currdoy < 100:
                dayofyear = '0' + str(currdoy)
            else:
                dayofyear = str(currdoy)

            # NCEP REANALYSIS file
            ncepFile = ("%s/REANALYSIS/RE_%d/REANALYSIS_%d%s.hdf"
                        % (ancdir, year, year, dayofyear))

            # EP/TOMS file
            tomsFile = ("%s/EP_TOMS/ozone_%d/TOMS_%d%s.hdf"
                        % (ancdir, year, year, dayofyear))
            if os.path.isfile(ncepFile) and os.path.isfile(tomsFile):
                doyList.append(True)
            else:
                doyList.append(False)

        # return the True/False list
        return doyList

    ########################################################################
    # Description: runLedaps will use the parameter passed for the xmlfile.
    # If xmlfile is None (i.e. not specified) then the command-line parameters
    # will be parsed for this information.  The LEDAPS applications are then
    # executed on the specified XML file.  If a log file was specified, then
    # the output from each LEDAPS application will be logged to that file.
    #
    # Inputs:
    #   xmlfile - name of the Landsat XML file to be processed
    #   process_sr - specifies whether the surface reflectance processing,
    #       should be completed.  True or False.  Default is True, otherwise
    #       the processing will halt after the TOA reflectance products are
    #       complete.
    #
    # Returns:
    #     ERROR - error running the LEDAPS applications
    #     SUCCESS - successful processing
    #
    # Notes:
    #   1. The script obtains the path of the XML file and changes
    #      directory to that path for running the LEDAPS code.  If the
    #      xmlfile directory is not writable, then this script exits with
    #      an error.
    #######################################################################
    def runLedaps(self, xmlfile=None, process_sr="True"):
        # if no parameters were passed then get the info from the
        # command line
        if xmlfile is None:
            # get the command line argument for the XML file
            parser = OptionParser()
            parser.add_option("-f", "--xml",
                              type="string", dest="xmlfile",
                              help="name of Landsat XML file",
                              metavar="FILE")
            parser.add_option("-s", "--process_sr", type="string",
                              dest="process_sr",
                              help=("process the surface reflectance products;"
                                    " True or False (default is True) "
                                    " If False, then processing will halt"
                                    " after the TOA reflectance products are"
                                    " complete. (Note: scenes with solar"
                                    " zenith angles above 76 degrees should"
                                    " use process_sr=False)"))
            (options, args) = parser.parse_args()

            # validate the command-line options
            xmlfile = options.xmlfile  # name of the XML file
            if xmlfile is None:
                parser.error("missing xmlfile command-line argument")
                return ERROR
            process_sr = options.process_sr  # process SR or not
            if process_sr is None:
                process_sr = "True"  # If not provided, default to True

        # Obtain logger from logging using the module's name
        logger = logging.getLogger(__name__)
        logger.info('LEDAPS processing of Landsat XML file: {0}'
                    .format(xmlfile))

        # make sure the XML file exists
        if not os.path.isfile(xmlfile):
            logger.error('XML file does not exist or is not accessible'
                         ': {0}'.format(xmlfile))
            return ERROR

        # parse the XML filename, strip off the .xml
        # use the base XML filename and not the full path.
        base_xmlfile = os.path.basename(xmlfile)
        xml = re.sub('\.xml$', '', base_xmlfile)
        logger.info('Processing XML basefile: {0}'.format(xml))

        # get the path of the XML file and change directory to that location
        # for running this script.  save the current working directory for
        # return to upon error or when processing is complete.  Note: use
        # abspath to handle the case when the filepath is just the filename
        # and doesn't really include a file path (i.e. the current working
        # directory).
        mydir = os.getcwd()
        xmldir = os.path.dirname(os.path.abspath(xmlfile))
        if not os.access(xmldir, os.W_OK):
            logger.error('Path of XML file is not writable: {0}.'
                         '  LEDAPS needs write access to the XML directory.'
                         .format(xmldir))
            return ERROR
        logger.info('Changing directories for LEDAPS processing: {0}'
                    .format(xmldir))
        os.chdir(xmldir)

        # determine if this scene is pre-collection or a collection scene
        prefixes_old = ['LT4', 'LT5', 'LE7']
        prefixes_collection = ['LT04', 'LT05', 'LE07']
        if base_xmlfile[0:3] in prefixes_old:
            # Old-style (pre-collection) Level-1 naming convention
            processing_collection = False
            logger.debug('Processing pre-collection data')
        elif base_xmlfile[0:4] in prefixes_collection:
            # New-style collection naming convention
            processing_collection = True
            logger.debug('Processing collection data')
        else:
            msg = ('Base XML filename is not recognized as a valid Landsat 4-7 '
                   'scene name' + base_xmlfile)
            logger.error (msg)
            os.chdir (mydir)
            return ERROR

        # set up the command-line option for lndsr for processing collections.
        # if processing collections, then the per-pixel angle bands need to
        # be generated for band 4 (representative band) and the thermal band(s)
        process_collection_opt_str = ""
        if processing_collection:
            process_collection_opt_str = "--process_collection"

            cmdstr = "create_landsat_angle_bands --xml %s" % (base_xmlfile)
#            logger.debug('per-pixel angles command: {0}'.format(cmdstr))
            (status, output) = commands.getstatusoutput(cmdstr)
            logger.info(output)
            exit_code = status >> 8
            if exit_code != 0:
                logger.error('Error running create_landsat_angle_bands.'
                             '  Processing will terminate.')
                os.chdir(mydir)
                return ERROR

        # set up the command-line option for lndpm if processing surface
        # reflectance
        if process_sr == "True":
            process_sr_opt_str = "--process_sr=true"
        else:
            process_sr_opt_str = "--process_sr=false"

        # run LEDAPS modules, checking the return status of each module.
        # exit if any errors occur.
        cmdstr = "lndpm --xml %s %s" % (base_xmlfile, process_sr_opt_str)
        logger.debug('lndpm command: {0}'.format(cmdstr))
        (status, output) = commands.getstatusoutput(cmdstr)
        logger.info(output)
        exit_code = status >> 8
        if exit_code != 0:
            logger.error('Error running lndpm.  Processing will terminate.')
            os.chdir(mydir)
            return ERROR

        cmdstr = "lndcal --pfile lndcal.%s.txt %s" % (xml,
            process_collection_opt_str)
        # logger.debug('lndcal command: {0}'.format(cmdstr))
        (status, output) = commands.getstatusoutput(cmdstr)
        logger.info(output)
        exit_code = status >> 8
        if exit_code != 0:
            logger.error('Error running lndcal.  Processing will terminate.')
            os.chdir(mydir)
            return ERROR

        if process_sr == "True":
            cmdstr = "lndsr --pfile lndsr.%s.txt %s" % (xml,
                process_collection_opt_str)
#            logger.debug('lndsr command: {0}'.format(cmdstr))
            (status, output) = commands.getstatusoutput(cmdstr)
            logger.info(output)
            exit_code = status >> 8
            if exit_code != 0:
                logger.error('Error running lndsr.'
                             '  Processing will terminate.')
                os.chdir(mydir)
                return ERROR

            if not processing_collection:
                cmdstr = "lndsrbm.py -f lndsr.%s.txt" % xml
                # logger.debug('lndsrbm command: {0}'.format(cmdstr))
                (status, output) = commands.getstatusoutput(cmdstr)
                logger.info(output)
                exit_code = status >> 8
                if exit_code != 0:
                    logger.error('Error running lndsrbm.'
                                '  Processing will terminate.')
                    os.chdir(mydir)
                    return ERROR

        # successful completion.  return to the original directory.
        os.chdir(mydir)
        logger.info('Completion of LEDAPS.')
        return SUCCESS

# ##### end of Ledaps class #####

if __name__ == "__main__":
    # setup the default logger format and level. log to STDOUT.
    logging.basicConfig(format=('%(asctime)s.%(msecs)03d %(process)d'
                                ' %(levelname)-8s'
                                ' %(filename)s:%(lineno)d:'
                                '%(funcName)s -- %(message)s'),
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)
    sys.exit(Ledaps().runLedaps())
