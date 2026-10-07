// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;
contract RiskOracle {
    address public owner;
    mapping(address=>uint256) public prices;
    modifier onlyOwner(){require(msg.sender==owner,"OWNER");_;}
    constructor(){owner=msg.sender;}
    function setPrice(address t,uint256 p) external onlyOwner{require(p>0,"PRICE");prices[t]=p;}
    function price(address t) external view returns(uint256){uint256 p=prices[t];require(p>0,"NO_PRICE");return p;}
}
