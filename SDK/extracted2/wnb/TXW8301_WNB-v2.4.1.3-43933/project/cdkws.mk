.PHONY: clean All Project_Title Project_PreBuild Project_Build Project_PostBuild

All: Project_Title Project_PreBuild Project_Build Project_PostBuild

Project_Title:
	@echo "----------Building project:[ txw4002a - BuildSet ]----------"

Project_PreBuild:
	@echo Executing Pre Build commands ...
	@export CDKPath="D:/Soft/C-SKY" CDK_VERSION="V2.8.8" ProjectPath="D:/Halow/T-Halow/SDK/extracted2/wnb/TXW8301_WNB-v2.4.1.3-43933/project/" && D:/Halow/T-Halow/SDK/extracted2/wnb/TXW8301_WNB-v2.4.1.3-43933/project/prebuild.sh $<
	@echo Done

Project_Build:
	@make -r -f txw4002a.mk -C  ./ 

Project_PostBuild:
	@echo Executing Post Build commands ...
	@export CDKPath="D:/Soft/C-SKY" CDK_VERSION="V2.8.8" ProjectPath="D:/Halow/T-Halow/SDK/extracted2/wnb/TXW8301_WNB-v2.4.1.3-43933/project/" && D:/Halow/T-Halow/SDK/extracted2/wnb/TXW8301_WNB-v2.4.1.3-43933/project/BuildBIN.sh
	@echo Done


clean:
	@echo "----------Cleaning project:[ txw4002a - BuildSet ]----------"

